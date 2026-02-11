from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.text import Text
from rich.theme import Theme
from rich.align import Align
from typing import List, Optional

# 테마 설정
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "header": "bold magenta",
})

console = Console(theme=custom_theme)

class UIHelper:
    """Rich 라이브러리를 사용한 고품격 콘솔 UI 헬퍼 클래스"""
    
    @staticmethod
    def print_banner():
        """화려한 시작 배너 출력"""
        banner_text = Text.assemble(
            ("     _   _                      _   _  _              \n", "header"),
            ("    | \\ | |                    | | (_)| |             \n", "header"),
            ("    |  \\| |  ___ __   __  ___  | |  _ | |_  ___       \n", "header"),
            ("    | . ` | / _ \\\\ \\ / / / _ \\ | | | || __|/ _ \\      \n", "header"),
            ("    | |\\  || (_) |\\ V / |  __/ | | | || |_|  __/      \n", "header"),
            ("    |_| \\_| \\___/  \\_/   \\___| |_| |_| \\__|\\___|      \n", "header"),
            ("                    - AIze-SSR v3.0 -                 \n", "info")
        )
        
        panel = Panel(
            Align.center(banner_text),
            border_style="magenta",
            title="[bold white]NovelAIze-SSR[/bold white]",
            subtitle="[italic white]Advanced Novel Process Engine[/italic white]"
        )
        console.print(panel)
    
    @staticmethod
    def print_file_info(filename: str, size_mb: float, estimated_chapters: int):
        """파일 정보를 담은 세련된 테이블 출력"""
        table = Table(title="[bold white]📂 File Analysis[/bold white]", show_header=False, border_style="cyan")
        table.add_row("📄 [cyan]Filename[/cyan]", f"[bold]{filename}[/bold]")
        table.add_row("📏 [cyan]File Size[/cyan]", f"{size_mb:.2f} MB")
        table.add_row("📖 [cyan]Est. Chapters[/cyan]", f"~{estimated_chapters} chapters")
        
        console.print(table)
    
    @staticmethod
    def create_progress():
        """작업용 Rich Progress 객체 생성"""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            transient=True
        )

    @staticmethod
    def print_step_header(step_num: int, total_steps: int, description: str):
        """현재 진행 중인 대형 단계 헤더"""
        console.print(f"\n[header][{step_num}/{total_steps}][/header] [bold white]{description}[/bold white]")

    @staticmethod
    def print_completion(output_file: str, total_chapters: int, total_time: float, speed: float):
        """최종 성공 대시보드 출력"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_row("🚀 [success]Output File[/success]", f"[white]{output_file}[/white]")
        table.add_row("📊 [success]Processed[/success]", f"[white]{total_chapters} chapters[/white]")
        table.add_row("⏱️  [success]Total Time[/success]", f"[white]{total_time:.1f} seconds[/white]")
        table.add_row("✨ [success]Throughput[/success]", f"[white]{speed:.2f} chap/sec[/white]")
        
        panel = Panel(
            table,
            title="[bold green]✅ TASK COMPLETED SUCCESSFULLY[/bold green]",
            border_style="green",
            expand=False
        )
        console.print("\n", panel)
    
    @staticmethod
    def print_error(message: str):
        """주목도 높은 에러 패널 출력"""
        panel = Panel(
            f"[bold white]{message}[/bold white]",
            title="[bold red]❌ ERROR[/bold red]",
            border_style="red"
        )
        console.print("\n", panel)

    @staticmethod
    def print_success(message: str):
        """심플한 성공 메시지"""
        console.print(f"[success]✅ {message}[/success]")

    @staticmethod
    def print_warning(message: str):
        """경고 메시지"""
        console.print(f"[warning]⚠️  {message}[/warning]")

    @staticmethod
    def print_info(message: str):
        """정보 메시지"""
        console.print(f"[info]ℹ️  {message}[/info]")

