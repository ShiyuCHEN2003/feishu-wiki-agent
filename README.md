# 飞书知识库管理 Agent

基于 Claude AI 的飞书（Lark）知识库自动化整理工具，面向算法组知识库管理场景。

## 功能

- **智能扫描**：读取知识库完整文档树及正文内容，调用 Claude 进行语义分析
- **命名规范检查**：根据文档内容推断类型，生成符合规范的重命名建议（格式：`[类型] 文档名`）
- **目录结构优化**：识别放错位置的文档，建议移入对应分类目录
- **重复文档检测**：发现主题重叠的文档并给出合并建议
- **子文档目录生成**：为父级目录文档自动写入子文档链接列表及内容说明
- **操作确认机制**：所有写操作（重命名/移动/写入）均需用户逐条确认，不支持批量执行
- **操作日志**：每次确认执行的操作均记录到本地日志

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制示例配置并填写：

```bash
cp .env.example .env
```

编辑 `.env`：

```ini
FEISHU_APP_ID=        # 飞书应用 App ID
FEISHU_APP_SECRET=    # 飞书应用 App Secret
FEISHU_WIKI_SPACE_ID= # 知识库 Space ID
ANTHROPIC_API_KEY=    # Claude API Key

# 可选
FEISHU_DOMAIN=        # 飞书域名，如 yourcompany.feishu.cn（用于生成子文档链接）
FEISHU_CATEGORIES=    # 分类目录，格式：名称:node_token,名称:node_token
FEISHU_ARCHIVE_PARENT_TOKEN= # 归档目录 node_token
HTTPS_PROXY=          # Anthropic API 代理（如需要）
```

### 3. 飞书应用权限

在飞书开放平台为应用开启以下权限：

- `wiki:wiki` — 知识库读取
- `wiki:wiki:write` — 知识库写入（移动节点）
- `docx:document` — 文档读取
- `docx:document:write` — 文档写入（重命名、写入内容）

### 4. 运行

```bash
python agent.py
```

## 使用方式

```
> scan          # 扫描知识库，分析问题
> 日志          # 查看最近操作记录
> help          # 查看帮助

# 确认流程中：
> y             # 执行当前建议操作
> n             # 跳过
> q             # 取消全部，返回待机
```

## 项目结构

```
agent.py          # 交互式命令行入口
analyzer.py       # Claude AI 分析模块
feishu_client.py  # 飞书 API 客户端
workflow.py       # 状态机与操作执行
config.py         # 配置加载
models.py         # 数据模型
logger.py         # 操作日志
tests/            # 单元测试
```

## 技术栈

- [Anthropic Claude](https://www.anthropic.com/) — 文档语义分析
- [飞书开放平台 API](https://open.feishu.cn/document/home/index) — Wiki v2 / Docx v1
- [Rich](https://github.com/Textualize/rich) — 终端 UI

## 注意事项

- `.env` 文件包含密钥，**不要提交到代码库**
- 每个操作均需手动确认，Agent 不会自动批量执行
- 文档内容只读取前 300 字用于分析，不会修改正文（子文档目录生成除外）
