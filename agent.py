import sys
from rich.console import Console
from rich.panel import Panel
from config import load_config
from feishu_client import FeishuClient
from analyzer import Analyzer
from logger import Logger
from workflow import WorkflowEngine, State
from models import Issue

console = Console()

_SEVERITY_COLOR = {"high": "red", "medium": "yellow", "low": "blue"}

_HELP_TEXT = """
可用命令：
  扫描 / scan        — 扫描知识库，分析文档问题
  查看日志 / 日志    — 显示最近操作记录
  帮助 / help        — 显示此帮助

确认流程中的命令：
  y / 确认 / 同意   — 执行当前建议操作
  n / 跳过          — 跳过当前条目
  q / 取消全部      — 中止整个整理流程
"""


def parse_intent(text: str) -> str:
    t = text.strip().lower()
    if t in ("扫描", "scan"):
        return "scan"
    if t in ("查看日志", "日志", "log", "logs"):
        return "log"
    if t in ("帮助", "help"):
        return "help"
    if t in ("确认", "同意", "yes", "y"):
        return "confirm"
    if t in ("跳过", "skip", "n"):
        return "skip"
    if t in ("取消全部", "取消", "cancel", "quit", "q"):
        return "cancel"
    return "unknown"


def format_issue(issue: Issue, index: int, total: int, flat: list[dict] | None = None) -> str:
    color = _SEVERITY_COLOR.get(issue.severity, "white")
    severity_label = {"high": "高优先级", "medium": "中优先级", "low": "低优先级"}.get(issue.severity, "")
    type_label = {"naming": "命名不规范", "structure": "结构问题", "duplicate": "主题重复", "index": "缺少子文档目录"}.get(issue.type, issue.type)

    lines = [f"问题 {index}/{total} · {type_label} · [{color}]{severity_label}[/{color}]"]
    lines.append("─" * 45)

    if issue.type == "duplicate":
        lines.append("涉及文档：")
        for t in issue.current_titles:
            lines.append(f"  · {t}")
    elif issue.type == "index":
        lines.append(f"文档：{issue.current_title}")
        lines.append("将写入以下子文档目录：")
        for child in issue.child_index:
            lines.append(f"  · {child['title']}")
            lines.append(f"    {child['description']}")
    else:
        lines.append(f"文档：{issue.current_title}")
        if flat and issue.node_token:
            children = [e["title"] for e in flat if e.get("parent") == issue.node_token]
            if children:
                lines.append("子文档：")
                for c in children:
                    lines.append(f"  · {c}")

    lines.append("")
    if issue.target_parent_token:
        lines.append(f"操作：将此文档移动到 → {issue.suggestion}")
    else:
        lines.append(f"建议操作：{issue.suggestion}")
    lines.append(f"理由：{issue.reason}")
    lines.append("")
    lines.append("[y] 执行  [n] 跳过  [q] 取消全部")
    return "\n".join(lines)


def _show_scan_summary(engine: WorkflowEngine) -> None:
    issues = engine.pending_issues
    high = sum(1 for i in issues if i.severity == "high")
    mid = sum(1 for i in issues if i.severity == "medium")
    low = sum(1 for i in issues if i.severity == "low")
    duplicates = sum(1 for i in issues if i.type == "duplicate")
    naming = sum(1 for i in issues if i.type == "naming")
    structure = sum(1 for i in issues if i.type == "structure")
    console.print(Panel(
        f"节点总数：{engine.last_scan_node_count}   问题数：{len(issues)}\n\n"
        f"[red][高] ×{high}  主题重复 ×{duplicates}[/red]\n"
        f"[yellow][中] ×{mid}  命名不规范 ×{naming}[/yellow]\n"
        f"[blue][低] ×{low}  结构问题 ×{structure}[/blue]",
        title="扫描报告",
        border_style="cyan",
    ))


def run(engine: WorkflowEngine) -> None:
    console.print(Panel(
        "[bold cyan]飞书知识库管理 Agent（算法组）[/bold cyan]\n输入 help 查看可用命令",
        border_style="cyan",
    ))
    while True:
        try:
            prompt = "[y/n/q]> " if engine.state == State.CONFIRM else "> "
            text = console.input(f"[bold green]{prompt}[/bold green]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]已退出。[/dim]")
            break

        intent = parse_intent(text)

        if engine.state == State.CONFIRM:
            issue = engine.current_issue()
            if issue and intent == "confirm":
                console.print("[green]✓ 正在执行...[/green]")
                err = engine.confirm_current()
                if err:
                    console.print(f"[red]✗ 执行失败：{err}[/red]")
                else:
                    console.print("[green]✓ 已执行并记录日志[/green]")
                if engine.state == State.CONFIRM:
                    nxt = engine.current_issue()
                    if nxt:
                        console.print(format_issue(nxt, engine.current_index + 1, len(engine.pending_issues)))
            elif intent == "skip":
                engine.skip_current()
                console.print("[dim]已跳过[/dim]")
                if engine.state == State.CONFIRM:
                    nxt = engine.current_issue()
                    if nxt:
                        console.print(format_issue(nxt, engine.current_index + 1, len(engine.pending_issues)))
            elif intent == "cancel":
                engine.cancel_all()
                console.print("[yellow]已取消全部，返回待机状态[/yellow]")
            else:
                console.print("[dim]请输入 y（执行）/ n（跳过）/ q（取消全部）[/dim]")
            continue

        if intent == "scan":
            console.print("[cyan]正在扫描知识库...[/cyan]")
            engine.start_scan()
            if engine.state == State.CONFIRM:
                _show_scan_summary(engine)
                issue = engine.current_issue()
                if issue:
                    console.print(format_issue(issue, 1, len(engine.pending_issues)))
            else:
                console.print(f"[green]✓ 扫描完成，共扫描 {engine.last_scan_node_count} 个节点，未发现问题[/green]")
        elif intent == "log":
            entries = engine._logger.read_recent(n=10)
            if not entries:
                console.print("[dim]暂无操作记录[/dim]")
            else:
                for e in entries:
                    console.print(
                        f"[dim]{e['timestamp']}[/dim] [{e['action']}] "
                        f"{e.get('from', '')} → {e.get('to', '')} "
                        f"(issue: {e['issue_id']})"
                    )
        elif intent == "help":
            console.print(_HELP_TEXT)
        else:
            console.print("[dim]未识别的命令，输入 help 查看帮助[/dim]")


def main() -> None:
    try:
        config = load_config()
    except ValueError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        console.print("请复制 .env.example 为 .env 并填写配置项")
        sys.exit(1)
    feishu = FeishuClient(config)
    analyzer = Analyzer(api_key=config.anthropic_api_key, categories=config.categories)
    logger = Logger()
    engine = WorkflowEngine(
        feishu_client=feishu,
        analyzer=analyzer,
        logger=logger,
        archive_parent_token=config.archive_parent_token,
    )
    run(engine)


if __name__ == "__main__":
    main()
