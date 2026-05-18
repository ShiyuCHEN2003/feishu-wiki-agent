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
  确认 / 同意        — 执行当前建议操作
  跳过               — 跳过当前条目
  取消全部           — 中止整个整理流程
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
    if t in ("跳过", "skip"):
        return "skip"
    if t in ("取消全部", "取消", "cancel", "quit", "q"):
        return "cancel"
    return "unknown"


def format_issue(issue: Issue, index: int, total: int) -> str:
    color = _SEVERITY_COLOR.get(issue.severity, "white")
    severity_label = {"high": "高优先级", "medium": "中优先级", "low": "低优先级"}.get(issue.severity, "")
    type_label = {"naming": "命名不规范", "structure": "结构问题", "duplicate": "主题重复"}.get(issue.type, issue.type)

    lines = [f"问题 {index}/{total} · {type_label} · [{color}]{severity_label}[/{color}]"]
    lines.append("─" * 45)

    if issue.type == "duplicate":
        lines.append("涉及文档：")
        for t in issue.current_titles:
            lines.append(f"  · {t}")
    else:
        lines.append(f"文档：{issue.current_title}")

    lines.append("")
    lines.append(f"建议操作：{issue.suggestion}")
    lines.append(f"理由：{issue.reason}")
    lines.append("")
    lines.append("输入「确认」执行 / 「跳过」保留 / 「取消全部」中止")
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
            prompt = "确认/跳过/取消> " if engine.state == State.CONFIRM else "> "
            text = console.input(f"[bold green]{prompt}[/bold green]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]已退出。[/dim]")
            break

        intent = parse_intent(text)

        if engine.state == State.CONFIRM:
            issue = engine.current_issue()
            if issue and intent == "confirm":
                console.print("[green]✓ 正在执行...[/green]")
                engine.confirm_current()
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
                console.print("[dim]请输入「确认」「跳过」或「取消全部」[/dim]")
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
                console.print("[green]✓ 扫描完成，未发现问题[/green]")
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
    analyzer = Analyzer(api_key=config.anthropic_api_key)
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
