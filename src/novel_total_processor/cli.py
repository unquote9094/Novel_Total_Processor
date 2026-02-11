"""CLI 인터페이스

Typer 기반 명령줄 인터페이스, Rich 기반 TUI
"""

import typer
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.db.schema import get_database
from novel_total_processor.stages.stage0_indexing import FileScanner
from novel_total_processor.stages.stage1_metadata import MetadataCollector
from novel_total_processor.stages.stage2_episode import EpisodePatternDetector
from novel_total_processor.stages.stage3_filename import FilenameGenerator
from novel_total_processor.stages.stage5_epub import EPUBGenerator

logger = get_logger(__name__)
console = Console()
app = typer.Typer(help="Novel Total Processor - 소설 파일 자동 처리 도구")


@app.command()
def index(
    folders: Optional[str] = typer.Option(None, "--folders", "-f", help="스캔할 폴더 (쉼표로 구분)"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="최대 파일 수")
):
    """Stage 0: 파일 인덱싱 (스캔 + 해시 + 중복 감지)"""
    console.print(Panel.fit("🔍 Stage 0: 파일 인덱싱", style="bold blue"))
    
    db = get_database()
    db.initialize_schema()
    
    scanner = FileScanner(db)
    
    folder_list = folders.split(",") if folders else None
    total, duplicates = scanner.run()
    
    # 결과 테이블
    table = Table(title="인덱싱 결과")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="green")
    table.add_row("총 파일", str(total))
    table.add_row("중복 파일", str(duplicates))
    
    console.print(table)
    db.close()


@app.command()
def metadata(
    limit: Optional[int] = typer.Option(10, "--limit", "-l", help="최대 파일 수"),
    batch_size: int = typer.Option(10, "--batch", "-b", help="배치 크기")
):
    """Stage 1: 메타데이터 수집 (Gemini + Perplexity)"""
    console.print(Panel.fit("📚 Stage 1: 메타데이터 수집", style="bold blue"))
    
    db = get_database()
    collector = MetadataCollector(db)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]메타데이터 추출 중...", total=limit)
        
        results = collector.run(limit=limit, batch_size=batch_size)
        progress.update(task, completed=results["total"])
    
    # 결과 테이블
    table = Table(title="메타데이터 수집 결과")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="green")
    table.add_row("총 파일", str(results["total"]))
    table.add_row("성공", str(results["success"]))
    table.add_row("실패", str(results["failed"]))
    
    console.print(table)
    db.close()


@app.command()
def episode(
    limit: Optional[int] = typer.Option(5, "--limit", "-l", help="최대 파일 수")
):
    """Stage 2: 화수 검증 (AI 패턴 감지)"""
    console.print(Panel.fit("🔢 Stage 2: 화수 검증", style="bold blue"))
    
    db = get_database()
    detector = EpisodePatternDetector(db)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]화수 패턴 감지 중...", total=limit)
        
        results = detector.run(limit=limit)
        progress.update(task, completed=results["total"])
    
    # 결과 테이블
    table = Table(title="화수 검증 결과")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="green")
    table.add_row("총 파일", str(results["total"]))
    table.add_row("성공", str(results["success"]))
    table.add_row("실패", str(results["failed"]))
    
    console.print(table)
    db.close()


@app.command()
def filename(
    limit: Optional[int] = typer.Option(10, "--limit", "-l", help="최대 파일 수")
):
    """Stage 3: 파일명 생성 (규칙 엔진)"""
    console.print(Panel.fit("📝 Stage 3: 파일명 생성", style="bold blue"))
    
    db = get_database()
    generator = FilenameGenerator(db)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]파일명 생성 중...", total=limit)
        
        results = generator.run(limit=limit)
        progress.update(task, completed=results["total"])
    
    # 결과 테이블
    table = Table(title="파일명 생성 결과")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="green")
    table.add_row("총 파일", str(results["total"]))
    table.add_row("매핑 파일", results["mapping_file"] or "없음")
    
    console.print(table)
    
    if results["mapping_file"]:
        console.print(f"\n✅ 매핑 파일을 확인하세요: [green]{results['mapping_file']}[/green]")
    
    db.close()


@app.command()
def epub(
    limit: Optional[int] = typer.Option(3, "--limit", "-l", help="최대 파일 수")
):
    """Stage 5: EPUB 생성"""
    console.print(Panel.fit("📖 Stage 5: EPUB 생성", style="bold blue"))
    
    db = get_database()
    generator = EPUBGenerator(db)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]EPUB 생성 중...", total=limit)
        
        results = generator.run(limit=limit)
        progress.update(task, completed=results["total"])
    
    # 결과 테이블
    table = Table(title="EPUB 생성 결과")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="green")
    table.add_row("총 파일", str(results["total"]))
    table.add_row("성공", str(results["success"]))
    table.add_row("실패", str(results["failed"]))
    
    console.print(table)
    
    if results["success"] > 0:
        console.print(f"\n✅ EPUB 파일이 생성되었습니다: [green]{generator.output_dir}[/green]")
    
    db.close()


@app.command()
def pipeline(
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="최대 파일 수"),
    skip_index: bool = typer.Option(False, "--skip-index", help="인덱싱 건너뛰기"),
    skip_metadata: bool = typer.Option(False, "--skip-metadata", help="메타데이터 건너뛰기"),
    skip_episode: bool = typer.Option(False, "--skip-episode", help="화수 검증 건너뛰기"),
    skip_filename: bool = typer.Option(False, "--skip-filename", help="파일명 생성 건너뛰기"),
):
    """전체 파이프라인 실행 (Stage 0 → 1 → 2 → 3 → 5)"""
    console.print(Panel.fit("🚀 전체 파이프라인 실행", style="bold magenta"))
    
    db = get_database()
    db.initialize_schema()
    
    # Stage 0: 인덱싱
    if not skip_index:
        console.print("\n[bold blue]Stage 0: 파일 인덱싱[/bold blue]")
        scanner = FileScanner(db)
        total, duplicates = scanner.run()
        console.print(f"✅ {total}개 파일 인덱싱 완료 ({duplicates}개 중복)")
    
    # Stage 1: 메타데이터
    if not skip_metadata:
        console.print("\n[bold blue]Stage 1: 메타데이터 수집[/bold blue]")
        collector = MetadataCollector(db)
        results = collector.run(limit=limit)
        console.print(f"✅ {results['success']}/{results['total']} 파일 메타데이터 수집 완료")
    
    # Stage 2: 화수 검증
    if not skip_episode:
        console.print("\n[bold blue]Stage 2: 화수 검증[/bold blue]")
        detector = EpisodePatternDetector(db)
        results = detector.run(limit=limit)
        console.print(f"✅ {results['success']}/{results['total']} 파일 화수 검증 완료")
    
    # Stage 3: 파일명 생성
    if not skip_filename:
        console.print("\n[bold blue]Stage 3: 파일명 생성[/bold blue]")
        generator = FilenameGenerator(db)
        results = generator.run(limit=limit)
        console.print(f"✅ {results['total']} 파일 파일명 생성 완료")
        if results["mapping_file"]:
            console.print(f"   매핑 파일: {results['mapping_file']}")
    
    # Stage 5: EPUB 생성
    console.print("\n[bold blue]Stage 5: EPUB 생성[/bold blue]")
    epub_gen = EPUBGenerator(db)
    results = epub_gen.run(limit=limit)
    console.print(f"✅ {results['success']}/{results['total']} EPUB 생성 완료")
    
    console.print("\n[bold green]🎉 파이프라인 실행 완료![/bold green]")
    db.close()


@app.command()
def status():
    """처리 상태 확인"""
    console.print(Panel.fit("📊 처리 상태", style="bold blue"))
    
    db = get_database()
    conn = db.connect()
    cursor = conn.cursor()
    
    # 전체 통계
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
    
    table = Table(title="파이프라인 진행 상황")
    table.add_column("Stage", style="cyan")
    table.add_column("완료", style="green")
    table.add_column("비율", style="yellow")
    
    total = row[0] or 1
    table.add_row("Stage 0: 인덱싱", str(row[1]), f"{row[1]/total*100:.1f}%")
    table.add_row("Stage 1: 메타데이터", str(row[2]), f"{row[2]/total*100:.1f}%")
    table.add_row("Stage 2: 화수 검증", str(row[3]), f"{row[3]/total*100:.1f}%")
    table.add_row("Stage 3: 파일명", str(row[4]), f"{row[4]/total*100:.1f}%")
    table.add_row("Stage 5: EPUB", str(row[5]), f"{row[5]/total*100:.1f}%")
    
    console.print(table)
    db.close()


if __name__ == "__main__":
    app()
