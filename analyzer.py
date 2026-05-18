import json
import anthropic
from models import WikiNode, Issue

_NAMING_CONVENTION = """
文档命名规范：[类型][日期] 文档名（作者）
类型标签：[技术文档] [交接文档] [会议纪要] [实验报告] [归档]
日期格式：YYYY-MM（如 2026-05）
例：[技术文档][2026-03] SLAM模型部署指南（李四）
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
                        "type": {"type": "string", "enum": ["naming", "structure", "duplicate"]},
                        "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                        "suggestion": {"type": "string"},
                        "reason": {"type": "string"},
                        "node_token": {"type": "string", "default": ""},
                        "current_title": {"type": "string", "default": ""},
                        "node_tokens": {"type": "array", "items": {"type": "string"}, "default": []},
                        "current_titles": {"type": "array", "items": {"type": "string"}, "default": []},
                    },
                    "required": ["id", "type", "severity", "suggestion", "reason"],
                },
            }
        },
        "required": ["issues"],
    },
}


_SYSTEM_PROMPT = (
    "你是算法组知识库管理员助手。根据以下命名规范和结构分析维度，分析文档列表，"
    "找出所有问题，调用 report_issues 工具返回结果。\n\n"
    "命名规范：\n" + _NAMING_CONVENTION + "\n\n"
    "分析维度：\n"
    "1. 命名问题（naming）：不符合命名规范的文档\n"
    "2. 结构问题（structure）：内容与所在目录不匹配，或同级文档之间缺乏逻辑层次\n"
    "3. 重复问题（duplicate）：标题相似或内容主题重复的文档\n\n"
    "如果文档提供了 content 字段，请结合内容摘要判断：\n"
    "- 文档实际内容是否与其标题和所在目录一致\n"
    "- 是否存在内容高度相似的重复文档"
)


def _flatten(nodes: list[WikiNode], depth: int = 0) -> list[dict]:
    result = []
    for node in nodes:
        entry = {
            "node_token": node.node_token,
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


class Analyzer:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

    def analyze(self, tree: list[WikiNode]) -> list[Issue]:
        flat = _flatten(tree)
        tree_json = json.dumps(flat, ensure_ascii=False, indent=2)
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            tools=[_REPORT_ISSUES_TOOL],
            tool_choice={"type": "any"},
            system=_SYSTEM_PROMPT,
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
                        current_title=item.get("current_title", ""),
                        node_tokens=item.get("node_tokens", []),
                        current_titles=item.get("current_titles", []),
                    )
                    for item in block.input["issues"]
                ]
        return []
