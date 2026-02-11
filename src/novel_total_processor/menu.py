"""대화형 메뉴 TUI

Rich 기반 대화형 메뉴 인터페이스
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.db.schema import get_database
from novel_total_processor.stages.stage0_indexing import FileScanner
from novel_total_processor.stages.stage1_metadata import MetadataCollector
from novel_total_processor.stages.stage2_episode import EpisodePatternDetector
from novel_total_processor.stages.stage3_filename import FilenameGenerator
from novel_total_processor.stages.stage5_epub import EPUBGenerator

logger = get_logger(__name__)
console = Console()


class InteractiveMenu:
    """대화형 메뉴 TUI"""
    
    def __init__(self):
        self.db = get_database()
        self.db.initialize_schema()
    
    def show_banner(self):
        """배너 표시"""
        banner = """
[bold cyan]╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        📚 Novel Total Processor v0.1.0                   ║
║        소설 파일 자동 처리 파이프라인                    ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝[/bold cyan]
"""
        console.print(banner)
    
    def show_status(self):
        """현재 상태 표시"""
        console.print("\n[bold yellow]📊 현재 처리 상태[/bold yellow]")
        console.print("[dim]Current Processing Status[/dim]\n")
        
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(stage0_indexed) as indexed,
                SUM(stage1_meta) as metadata,
                SUM(stage2_episode) as episode,
                SUM(stage3_rename) as filename,
                SUM(stage5_epub) as epub
            FROM processing_state
        """)
        row = cursor.fetchone()
        
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("단계 (Stage)", style="cyan", width=30)
        table.add_column("완료 (Completed)", justify="right", style="green", width=15)
        table.add_column("비율 (Ratio)", justify="right", style="yellow", width=15)
        
        total = row[0] or 1
        
        stages = [
            ("Stage 0: 파일 인덱싱\n[dim]File Indexing[/dim]", row[1]),
            ("Stage 1: 메타데이터 수집\n[dim]Metadata Collection[/dim]", row[2]),
            ("Stage 2: 화수 검증\n[dim]Episode Verification[/dim]", row[3]),
            ("Stage 3: 파일명 생성\n[dim]Filename Generation[/dim]", row[4]),
            ("Stage 5: EPUB 생성\n[dim]EPUB Generation[/dim]", row[5]),
        ]
        
        for stage_name, count in stages:
            ratio = f"{count/total*100:.1f}%"
            table.add_row(stage_name, str(count), ratio)
        
        console.print(table)
    
    def show_menu(self):
        """메인 메뉴 표시"""
        console.print("\n[bold green]🎯 메뉴 (Menu)[/bold green]\n")
        
        menu_items = [
            "[1] 📁 파일 인덱싱 (File Indexing) - Stage 0",
            "[2] 📚 메타데이터 수집 (Metadata Collection) - Stage 1",
            "[3] 🔢 화수 검증 (Episode Verification) - Stage 2",
            "[4] 📝 파일명 생성 (Filename Generation) - Stage 3",
            "[5] 📖 EPUB 생성 (EPUB Generation) - Stage 5",
            "[6] 🚀 전체 파이프라인 실행 (Run Full Pipeline)",
            "[7] 📊 상태 확인 (Check Status)",
            "[0] 🚪 종료 (Exit)",
        ]
        
        for item in menu_items:
            console.print(f"  {item}")
    
    def run_stage0(self):
        """Stage 0 실행"""
        console.print(Panel.fit(
            "[bold blue]📁 Stage 0: 파일 인덱싱[/bold blue]\n"
            "[dim]File Indexing - Scanning folders and detecting duplicates[/dim]",
            border_style="blue"
        ))
        
        console.print("\n[yellow]설정된 폴더를 스캔하여 소설 파일을 찾고 중복을 감지합니다.[/yellow]")
        console.print("[dim]Scanning configured folders to find novel files and detect duplicates.[/dim]\n")
        
        if not Confirm.ask("계속 진행하시겠습니까? (Continue?)"):
            return
        
        scanner = FileScanner(self.db)
        
        console.print("\n[cyan]📂 폴더 스캔 중... (Scanning folders...)[/cyan]")
        total, duplicates = scanner.run()
        
        console.print(f"\n[bold green]✅ 완료! (Completed!)[/bold green]")
        console.print(f"  • 총 파일 수 (Total files): [green]{total}[/green]")
        console.print(f"  • 중복 파일 수 (Duplicates): [yellow]{duplicates}[/yellow]")
    
    def run_stage1(self):
        """Stage 1 실행"""
        console.print(Panel.fit(
            "[bold blue]📚 Stage 1: 메타데이터 수집[/bold blue]\n"
            "[dim]Metadata Collection - Extracting title, author, genre using AI[/dim]",
            border_style="blue"
        ))
        
        console.print("\n[yellow]Gemini AI를 사용하여 파일명에서 메타데이터를 추출합니다.[/yellow]")
        console.print("[dim]Using Gemini AI to extract metadata from filenames.[/dim]\n")
        
        limit = IntPrompt.ask(
            "처리할 파일 수를 입력하세요 (Enter number of files to process)",
            default=10
        )
        
        collector = MetadataCollector(self.db)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                "[cyan]메타데이터 추출 중... (Extracting metadata...)[/cyan]",
                total=limit
            )
            
            results = collector.run(limit=limit)
            progress.update(task, completed=results["total"])
        
        console.print(f"\n[bold green]✅ 완료! (Completed!)[/bold green]")
        console.print(f"  • 처리 파일 수 (Processed): [green]{results['total']}[/green]")
        console.print(f"  • 성공 (Success): [green]{results['success']}[/green]")
        console.print(f"  • 실패 (Failed): [red]{results['failed']}[/red]")
    
    def run_stage2(self):
        """Stage 2 실행"""
        console.print(Panel.fit(
            "[bold blue]🔢 Stage 2: 화수 검증[/bold blue]\n"
            "[dim]Episode Verification - Detecting episode patterns using AI[/dim]",
            border_style="blue"
        ))
        
        console.print("\n[yellow]파일 내용을 샘플링하여 실제 화수 범위를 AI로 감지합니다.[/yellow]")
        console.print("[dim]Sampling file content to detect actual episode range using AI.[/dim]\n")
        
        limit = IntPrompt.ask(
            "처리할 파일 수를 입력하세요 (Enter number of files to process)",
            default=5
        )
        
        detector = EpisodePatternDetector(self.db)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                "[cyan]화수 패턴 감지 중... (Detecting episode patterns...)[/cyan]",
                total=limit
            )
            
            results = detector.run(limit=limit)
            progress.update(task, completed=results["total"])
        
        console.print(f"\n[bold green]✅ 완료! (Completed!)[/bold green]")
        console.print(f"  • 처리 파일 수 (Processed): [green]{results['total']}[/green]")
        console.print(f"  • 성공 (Success): [green]{results['success']}[/green]")
        console.print(f"  • 실패 (Failed): [red]{results['failed']}[/red]")
    
    def run_stage3(self):
        """Stage 3 실행"""
        console.print(Panel.fit(
            "[bold blue]📝 Stage 3: 파일명 생성[/bold blue]\n"
            "[dim]Filename Generation - Creating standardized filenames[/dim]",
            border_style="blue"
        ))
        
        console.print("\n[yellow]규칙 엔진을 사용하여 표준화된 파일명을 생성합니다.[/yellow]")
        console.print("[dim]Using rule engine to generate standardized filenames.[/dim]\n")
        
        limit = IntPrompt.ask(
            "처리할 파일 수를 입력하세요 (Enter number of files to process)",
            default=10
        )
        
        generator = FilenameGenerator(self.db)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                "[cyan]파일명 생성 중... (Generating filenames...)[/cyan]",
                total=limit
            )
            
            results = generator.run(limit=limit)
            progress.update(task, completed=results["total"])
        
        console.print(f"\n[bold green]✅ 완료! (Completed!)[/bold green]")
        console.print(f"  • 처리 파일 수 (Processed): [green]{results['total']}[/green]")
        
        if results["mapping_file"]:
            console.print(f"  • 매핑 파일 (Mapping file): [cyan]{results['mapping_file']}[/cyan]")
            console.print("\n[yellow]💡 매핑 파일을 확인하여 파일명 변경 계획을 검토하세요.[/yellow]")
            console.print("[dim]Please review the mapping file to check the filename change plan.[/dim]")
    
    def run_stage5(self):
        """Stage 5 실행"""
        console.print(Panel.fit(
            "[bold blue]📖 Stage 5: EPUB 생성[/bold blue]\n"
            "[dim]EPUB Generation - Converting TXT files to EPUB format[/dim]",
            border_style="blue"
        ))
        
        console.print("\n[yellow]TXT 파일을 EPUB 전자책 형식으로 변환합니다.[/yellow]")
        console.print("[dim]Converting TXT files to EPUB e-book format.[/dim]\n")
        
        limit = IntPrompt.ask(
            "처리할 파일 수를 입력하세요 (Enter number of files to process)",
            default=3
        )
        
        epub_gen = EPUBGenerator(self.db)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                "[cyan]EPUB 생성 중... (Generating EPUB files...)[/cyan]",
                total=limit
            )
            
            results = epub_gen.run(limit=limit)
            progress.update(task, completed=results["total"])
        
        console.print(f"\n[bold green]✅ 완료! (Completed!)[/bold green]")
        console.print(f"  • 처리 파일 수 (Processed): [green]{results['total']}[/green]")
        console.print(f"  • 성공 (Success): [green]{results['success']}[/green]")
        console.print(f"  • 실패 (Failed): [red]{results['failed']}[/red]")
        
        if results["success"] > 0:
            console.print(f"\n  • 출력 폴더 (Output folder): [cyan]{epub_gen.output_dir}[/cyan]")
            console.print("\n[yellow]💡 생성된 EPUB 파일을 전자책 리더로 확인하세요.[/yellow]")
            console.print("[dim]Please check the generated EPUB files with an e-book reader.[/dim]")
    
    def run_pipeline(self):
        """전체 파이프라인 실행"""
        console.print(Panel.fit(
            "[bold magenta]🚀 전체 파이프라인 실행[/bold magenta]\n"
            "[dim]Full Pipeline - Running all stages sequentially[/dim]",
            border_style="magenta"
        ))
        
        console.print("\n[yellow]모든 단계를 순차적으로 실행합니다 (Stage 0 → 1 → 2 → 3 → 5).[/yellow]")
        console.print("[dim]Running all stages sequentially (Stage 0 → 1 → 2 → 3 → 5).[/dim]\n")
        
        limit = IntPrompt.ask(
            "처리할 파일 수를 입력하세요 (Enter number of files to process, 0 = all)",
            default=10
        )
        
        if limit == 0:
            limit = None
        
        if not Confirm.ask("전체 파이프라인을 실행하시겠습니까? (Run full pipeline?)"):
            return
        
        # Stage 0
        console.print("\n[bold blue]📁 Stage 0: 파일 인덱싱 (File Indexing)[/bold blue]")
        scanner = FileScanner(self.db)
        total, duplicates = scanner.run()
        console.print(f"✅ {total}개 파일 인덱싱 완료 ({duplicates}개 중복)")
        console.print(f"[dim]Indexed {total} files ({duplicates} duplicates)[/dim]")
        
        # Stage 1
        console.print("\n[bold blue]📚 Stage 1: 메타데이터 수집 (Metadata Collection)[/bold blue]")
        collector = MetadataCollector(self.db)
        results = collector.run(limit=limit)
        console.print(f"✅ {results['success']}/{results['total']} 파일 메타데이터 수집 완료")
        console.print(f"[dim]Collected metadata for {results['success']}/{results['total']} files[/dim]")
        
        # Stage 2
        console.print("\n[bold blue]🔢 Stage 2: 화수 검증 (Episode Verification)[/bold blue]")
        detector = EpisodePatternDetector(self.db)
        results = detector.run(limit=limit)
        console.print(f"✅ {results['success']}/{results['total']} 파일 화수 검증 완료")
        console.print(f"[dim]Verified episodes for {results['success']}/{results['total']} files[/dim]")
        
        # Stage 3
        console.print("\n[bold blue]📝 Stage 3: 파일명 생성 (Filename Generation)[/bold blue]")
        generator = FilenameGenerator(self.db)
        results = generator.run(limit=limit)
        console.print(f"✅ {results['total']} 파일 파일명 생성 완료")
        console.print(f"[dim]Generated filenames for {results['total']} files[/dim]")
        if results["mapping_file"]:
            console.print(f"   매핑 파일 (Mapping): {results['mapping_file']}")
        
        # Stage 5
        console.print("\n[bold blue]📖 Stage 5: EPUB 생성 (EPUB Generation)[/bold blue]")
        epub_gen = EPUBGenerator(self.db)
        results = epub_gen.run(limit=limit)
        console.print(f"✅ {results['success']}/{results['total']} EPUB 생성 완료")
        console.print(f"[dim]Generated {results['success']}/{results['total']} EPUB files[/dim]")
        
        console.print("\n[bold green]🎉 파이프라인 실행 완료! (Pipeline completed!)[/bold green]")
    
    def run(self):
        """메인 루프"""
        self.show_banner()
        
        while True:
            try:
                self.show_status()
                self.show_menu()
                
                choice = Prompt.ask(
                    "\n선택하세요 (Choose an option)",
                    choices=["0", "1", "2", "3", "4", "5", "6", "7"],
                    default="7"
                )
                
                if choice == "0":
                    console.print("\n[bold cyan]👋 프로그램을 종료합니다. (Exiting...)[/bold cyan]")
                    break
                elif choice == "1":
                    self.run_stage0()
                elif choice == "2":
                    self.run_stage1()
                elif choice == "3":
                    self.run_stage2()
                elif choice == "4":
                    self.run_stage3()
                elif choice == "5":
                    self.run_stage5()
                elif choice == "6":
                    self.run_pipeline()
                elif choice == "7":
                    continue  # 상태는 이미 표시됨
                
                console.print("\n" + "=" * 60)
                input("\n계속하려면 Enter를 누르세요... (Press Enter to continue...)")
                console.clear()
                self.show_banner()
                
            except KeyboardInterrupt:
                console.print("\n\n[bold yellow]⚠️ 사용자가 중단했습니다. (Interrupted by user)[/bold yellow]")
                if Confirm.ask("정말 종료하시겠습니까? (Really exit?)"):
                    break
            except Exception as e:
                console.print(f"\n[bold red]❌ 오류 발생 (Error occurred): {e}[/bold red]")
                logger.error(f"Menu error: {e}", exc_info=True)
                input("\n계속하려면 Enter를 누르세요... (Press Enter to continue...)")


def main():
    """메뉴 실행"""
    menu = InteractiveMenu()
    menu.run()


if __name__ == "__main__":
    main()
