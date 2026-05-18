import json
import os
import httpx
import anthropic
from models import WikiNode, Issue

_NAMING_CONVENTION = """
文档命名规范：[类型] 文档名
类型标签：[技术文档] [交接文档] [会议纪要] [实验报告] [归档]
例：[技术文档] SLAM模型部署指南
"""

_REPORT_ISSUES_TOOL = {
    "name": "report_issues",
    "description": "报告在知识库中发现的所有文档问题",
    "input_schema": {
        "type": "object",
        "properties": {
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string", "enum": ["naming", "structure", "duplicate", "index"]},
                        "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                        "suggestion": {"type": "string"},
                        "reason": {"type": "string"},
                        "node_token": {"type": "string", "default": ""},
                        "current_title": {"type": "string", "default": ""},
                        "node_tokens": {"type": "array", "items": {"type": "string"}, "default": []},
                        "current_titles": {"type": "array", "items": {"type": "string"}, "default": []},
                        "target_parent_token": {"type": "string", "default": ""},
                        "child_index": {
                            "type": "array",
                            "default": [],
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                                "required": ["title", "description"],
                            },
                        },
                    },
                    "required": ["id", "type", "severity", "suggestion", "reason"],
                },
            }
        },
        "required": ["issues"],
    },
}

_SYSTEM_PROMPT = (
    "你是知识库管理员助手。请逐一检查下面列表中 type=origin 的每个节点，"
    "找出所有问题，调用 report_issues 工具返回结果。\n\n"
    "【命名规范】：\n"
    + _NAMING_CONVENTION
    + "\n【命名检查规则】：\n"
    "- 只检查 type=origin 的节点，跳过 type=shortcut\n"
    "- 只要标题不以 [技术文档]、[交接文档]、[会议纪要]、[实验报告]、[归档] 之一开头，就是命名违规\n"
    "- 不论节点在第几层（depth=0/1/2/3...），规则一律适用\n"
    "- 「郝天 skill」「津帆 skill」「Person skill」这类个人文件夹标题同样违规\n"
    "- 「Xarm UI 使用教程」「底盘控制说明」「SDK 交接文档」等均违规，必须报告\n\n"
    "【命名建议格式（必须严格遵守）】：\n"
    "suggestion 字段格式：「重命名为 [类型] 文档名」\n"
    "- 类型：根据文档内容或标题判断（技术文档/交接文档/会议纪要/实验报告/归档）\n"
    "- 文档名：用内容理解后重新概括，要具体，不要照抄原标题\n"
    "- 示例：「Xarm UI 使用教程」→ suggestion: 「重命名为 [技术文档] xArm UI 操作使用指南」\n"
    "- 示例：「底盘控制说明」→ suggestion: 「重命名为 [技术文档] 底盘运动控制接口说明」\n\n"
    "【其他分析维度】：\n"
    "2. 结构问题（structure）：结合文档标题和内容，判断文档是否应移入更合适的分类目录\n"
    "3. 重复问题（duplicate）：标题相似或内容主题高度重复的文档\n"
    "4. 目录缺失（index）：有子文档的父节点，其正文应包含子文档的链接和说明，但目前缺失或不完整\n\n"
    "【index 类型要求】：\n"
    "对于每个含有子文档（depth 较浅、有子节点）的父节点，报告一个 type=index 的问题，并：\n"
    "- suggestion 填写：「为该目录补充子文档索引」\n"
    "- child_index 数组列出每个直接子文档：title 填子文档当前标题，description 根据子文档内容写一句话说明（如无内容则根据标题推断）\n"
    "- 示例 child_index 条目：{\"title\": \"xArm ROS2使用文档\", \"description\": \"介绍在ROS2环境下配置和控制xArm机械臂的完整流程\"}\n\n"
    "【严格要求】：\n"
    "- 必须逐一检查每个 origin 节点，不可跳过或省略\n"
    "- 本知识库几乎所有文档都不符合命名规范，请如实报告，不要因数量多而精简\n"
    "- 对于结构问题，suggestion 字段填写目标分类目录名称，target_parent_token 填写该目录的 token"
)


def _flatten(nodes: list[WikiNode], depth: int = 0) -> list[dict]:
    result = []
    for node in nodes:
        entry = {
            "node_token": node.node_token,
            "obj_token": node.obj_token,
            "title": node.title,
            "type": node.node_type,
            "parent": node.parent_node_token,
            "depth": depth,
        }
        if node.content:
            entry["content"] = node.content
        result.append(entry)
        if node.children:
            result.extend(_flatten(node.children, depth + 1))
    return result


def _build_system_prompt(categories: dict) -> str:
    if not categories:
        return _SYSTEM_PROMPT
    cat_lines = "\n".join(
        f"- {name}（token: {token}）" for name, token in categories.items()
    )
    return (
        _SYSTEM_PROMPT + "\n\n"
        "【知识库分类结构】以下是已有的分类文件夹，文档应归属到正确的类目下：\n"
        + cat_lines + "\n"
        "当发现某文档放错位置时，报告 type=structure 的问题，"
        "在 target_parent_token 字段填写目标类目的 token，suggestion 填写目标类目名称。"
    )


class Analyzer:
    def __init__(self, api_key: str, categories: dict = None) -> None:
        proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
        http_client = httpx.Client(proxy=proxy, timeout=httpx.Timeout(180.0, connect=10.0)) if proxy else None
        self._client = anthropic.Anthropic(api_key=api_key, http_client=http_client, timeout=180.0)
        self._categories = categories or {}

    def analyze(self, tree: list[WikiNode]) -> list[Issue]:
        flat = _flatten(tree)
        token_to_obj = {e["node_token"]: e.get("obj_token", "") for e in flat}
        tree_json = json.dumps(flat, ensure_ascii=False, indent=2)
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            tools=[_REPORT_ISSUES_TOOL],
            tool_choice={"type": "any"},
            system=_build_system_prompt(self._categories),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"以下是知识库节点列表（共 {len(flat)} 个），请分析问题：\n\n{tree_json}",
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            ],
        )
        title_to_token = {e["title"]: e["node_token"] for e in flat}
        for block in response.content:
            if block.type == "tool_use" and block.input.get("issues") is not None:
                return [
                    Issue(
                        id=item["id"],
                        type=item["type"],
                        severity=item["severity"],
                        suggestion=item["suggestion"],
                        reason=item["reason"],
                        node_token=item.get("node_token", ""),
                        obj_token=token_to_obj.get(item.get("node_token", ""), ""),
                        current_title=item.get("current_title", ""),
                        node_tokens=item.get("node_tokens", []),
                        current_titles=item.get("current_titles", []),
                        target_parent_token=item.get("target_parent_token", ""),
                        child_index=[
                            {**c, "node_token": title_to_token.get(c.get("title", ""), "")}
                            for c in item.get("child_index", [])
                        ],
                    )
                    for item in block.input["issues"]
                ]
        return []
