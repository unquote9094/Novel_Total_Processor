"""데이터베이스 뷰어 (TUI)

Rich 라이브러리를 활용한 고급 DB 뷰어
- 파일 목록 조회 (페이지네이션)
- 검색 (파일명, 제목, 작가)
- 필터 (단계별 완료 여부)
- 상세 보기 (메타데이터, 챕터 정보)
- 통계 대시보드
"""

import math
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.prompt import Prompt, IntPrompt, Confirm
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.db.schema import get_database

logger = get_logger(__name__)
console = Console()


class DBViewer:
    """데이터베이스 뷰어 클래스"""

    def __init__(self):
        self.db = get_database()
        self.page_size = 15
        self.current_page = 1
        self.total_pages = 1
        self.current_query = ""
        self.current_filter = "all"  # all, completed, incomplete, error
        
    def run(self):
        """뷰어 메인 루프"""
        while True:
            console.clear()
            self._show_header()
            
            # 데이터 조회
            files, total_count = self._fetch_files()
            self.total_pages = math.ceil(total_count / self.page_size) or 1
            
            # 테이블 표시
            self._show_file_list(files)
            self._show_footer(total_count)
            
            # 입력 처리
            cmd = Prompt.ask(
                "\n[bold cyan]명령어 입력[/bold cyan]",
                choices=["n", "p", "s", "f", "d", "t", "q", "r"],
                default="n"
            ).lower()
            
            if cmd == "q":
                break
            elif cmd == "n":  # Next page
                if self.current_page < self.total_pages:
                    self.current_page += 1
            elif cmd == "p":  # Prev page
                if self.current_page > 1:
                    self.current_page -= 1
            elif cmd == "s":  # Search
                self._handle_search()
            elif cmd == "f":  # Filter
                self._handle_filter()
            elif cmd == "d":  # Detail
                self._handle_detail()
            elif cmd == "t":  # Statistics
                self._show_stats()
            elif cmd == "r":  # Refresh
                continue
    
    def _show_header(self):
        """헤더 표시"""
        filter_text = {
            "all": "전체",
            "completed": "완료됨 (EPUB 존재)",
            "incomplete": "진행 중",
            "error": "오류 발생"
        }.get(self.current_filter, self.current_filter)
        
        info = f"[dim]검색어:[/dim] '{self.current_query}' | [dim]필터:[/dim] {filter_text}"
        
        console.print(Panel(
            Text(f"🔍 데이터베이스 뷰어 (DB Viewer)\n{info}", justify="center"),
            style="bold blue"
        ))
    
    def _show_footer(self, total_count: int):
        """푸터/도움말 표시"""
        console.print(f"\n[dim]Page {self.current_page}/{self.total_pages} (Total {total_count} files)[/dim]")
        
        help_text = """
[bold]조작키:[/bold]
[N]ext     : 다음 페이지
[P]rev     : 이전 페이지
[S]earch   : 검색 (파일명/제목/작가)
[F]ilter   : 필터 (전체/완료/진행중/오류)
[D]etail   : 상세 보기 (ID 입력)
[T]otal    : 전체 통계
[Q]uit     : 나가기
"""
        console.print(Panel(help_text.strip(), title="Help", border_style="dim"))
    
    def _fetch_files(self) -> tuple[List[Any], int]:
        """조건에 맞는 파일 목록 조회"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # 기본 쿼리
        query = """
            SELECT f.id, f.file_name, f.file_size, 
                   n.title, n.author, 
                   ps.stage0_indexed, ps.stage1_meta, ps.stage4_split, 
                   ps.stage2_episode, ps.stage3_rename, ps.stage5_epub,
                   ps.last_error
            FROM files f
            LEFT JOIN novels n ON f.id = n.id
            LEFT JOIN processing_state ps ON f.id = ps.file_id
            WHERE f.is_duplicate = 0
        """
        params = []
        
        # 검색 조건
        if self.current_query:
            query += " AND (f.file_name LIKE ? OR n.title LIKE ? OR n.author LIKE ?)"
            p = f"%{self.current_query}%"
            params.extend([p, p, p])
        
        # 필터 조건
        if self.current_filter == "completed":
            query += " AND ps.stage5_epub = 1"
        elif self.current_filter == "incomplete":
            query += " AND ps.stage5_epub = 0"
        elif self.current_filter == "error":
            query += " AND ps.last_error IS NOT NULL"
        
        # 전체 개수 조회
        count_query = f"SELECT COUNT(*) FROM ({query})"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]
        
        # 페이지네이션
        query += " ORDER BY f.id DESC LIMIT ? OFFSET ?"
        offset = (self.current_page - 1) * self.page_size
        params.extend([self.page_size, offset])
        
        cursor.execute(query, params)
        return cursor.fetchall(), total_count
    
    def _show_file_list(self, files: List[Any]):
        """파일 목록 테이블 출력"""
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("ID", justify="right", width=5)
        table.add_column("파일명", width=30)
        table.add_column("제목/작가", width=25)
        table.add_column("진행상황 (0-1-4-2-3-5)", justify="center", width=20)
        table.add_column("상태", justify="center", width=10)
        
        if not files:
            console.print("\n[yellow]  데이터가 없습니다.[/yellow]\n")
            return

        for row in files:
            f_id, f_name, size, title, author, s0, s1, s4, s2, s3, s5, err = row
            
            # 파일명 말줄임
            f_display = f_name if len(f_name) < 28 else f_name[:25] + "..."
            
            # 제목/작가
            meta_info = f"[bold]{title}[/bold]" if title else "-"
            if author:
                meta_info += f"\n[dim]{author}[/dim]"
                
            # 진행상황 (단계별 아이콘)
            stages = [s0, s1, s4, s2, s3, s5]
            progress = ""
            for s in stages:
                progress += "[green]●[/green]" if s else "[dim]○[/dim]"
            
            # 상태 메시지
            if s5:
                status = "[green]완료[/green]"
            elif err:
                status = "[red]오류[/red]"
            else:
                status = "[yellow]진행중[/yellow]"
            
            table.add_row(
                str(f_id),
                f_display,
                meta_info,
                progress,
                status
            )
            
        console.print(table)
    
    def _handle_search(self):
        """검색어 입력"""
        self.current_query = Prompt.ask("검색어 입력 (취소: Enter)").strip()
        self.current_page = 1
    
    def _handle_filter(self):
        """필터 선택"""
        choice = Prompt.ask(
            "필터 선택",
            choices=["all", "completed", "incomplete", "error"],
            default="all"
        )
        self.current_filter = choice
        self.current_page = 1
    
    def _handle_detail(self):
        """상세 보기 진입"""
        file_id = IntPrompt.ask("상세 정보를 볼 파일 ID 입력 (0: 취소)", default=0)
        if file_id > 0:
            self._show_file_detail(file_id)
            input("\n엔터를 누르면 목록으로 돌아갑니다...")

    def _show_file_detail(self, file_id: int):
        """파일 상세 정보 출력"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # 기본 정보 + 메타데이터
        cursor.execute("""
            SELECT f.*, n.*, ps.*
            FROM files f
            LEFT JOIN novels n ON f.id = n.id
            LEFT JOIN processing_state ps ON f.id = ps.file_id
            WHERE f.id = ?
        """, (file_id,))
        row = cursor.fetchone()
        
        if not row:
            console.print("[red]해당 ID의 파일을 찾을 수 없습니다.[/red]")
            return
        
        # Row를 딕셔너리로 변환 (sqlite3.Row 기능 활용)
        data = dict(row)
        
        console.clear()
        console.print(Panel(f"[bold]파일 상세 정보 (ID: {file_id})[/bold]", style="blue"))
        
        # 1. 파일 정보
        grid = Table.grid(expand=True)
        grid.add_column(style="dim", width=15)
        grid.add_column()
        grid.add_row("파일명", data['file_name'])
        grid.add_row("파일 경로", data['file_path'])
        grid.add_row("파일 크기", f"{data['file_size'] / 1024 / 1024:.2f} MB" if data['file_size'] else "N/A")
        grid.add_row("해시", data['file_hash'])
        console.print(Panel(grid, title="📁 파일 정보"))
        
        # 2. 메타데이터
        grid = Table.grid(expand=True)
        grid.add_column(style="dim", width=15)
        grid.add_column()
        grid.add_row("제목", data.get('title') or "-")
        grid.add_row("작가", data.get('author') or "-")
        grid.add_row("장르", data.get('genre') or "-")
        grid.add_row("태그", data.get('tags') or "-")
        grid.add_row("완결 여부", data.get('status') or "-")
        grid.add_row("EPUB 경로", data.get('epub_path') or "-")
        console.print(Panel(grid, title="📚 메타데이터"))
        
        # 3. 챕터 정보 (캐시 확인 또는 Schema fallback)
        chapter_info = "정보 없음"
        if data.get('chapter_count'):
            chapter_info = f"총 {data['chapter_count']}화"
        
        console.print(Panel(chapter_info, title="✂️ 챕터 정보"))
        
        # 4. 처리 상태
        state_grid = Table(show_header=True)
        state_grid.add_column("단계")
        state_grid.add_column("상태")
        state_grid.add_column("오류 메시지")
        
        stages = [
            ("Stage 0 (인덱싱)", data['stage0_indexed']),
            ("Stage 1 (메타)", data['stage1_meta']),
            ("Stage 4 (분할)", data['stage4_split']),
            ("Stage 2 (검증)", data['stage2_episode']),
            ("Stage 3 (파일명)", data['stage3_rename']),
            ("Stage 5 (EPUB)", data['stage5_epub']),
        ]
        
        for name, done in stages:
            status = "[green]완료[/green]" if done else "[dim]대기[/dim]"
            msg = data['last_error'] if (data['last_error'] and not done and "Stage" in name) else "" # 단순화
            state_grid.add_row(name, status, msg)
            
        console.print(Panel(state_grid, title="⚙️ 처리 상태"))

    def _show_stats(self):
        """전체 통계 대시보드"""
        console.clear()
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # 전체 통계 쿼리
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(stage0_indexed) as s0,
                SUM(stage1_meta) as s1,
                SUM(stage4_split) as s4,
                SUM(stage2_episode) as s2,
                SUM(stage5_epub) as s5,
                SUM(CASE WHEN last_error IS NOT NULL THEN 1 ELSE 0 END) as errors
            FROM processing_state
        """)
        stats = cursor.fetchone()
        
        total = stats['total'] or 0
        if total == 0:
            console.print("[yellow]데이터가 없습니다.[/yellow]")
            input("\n엔터키를 누르면 돌아갑니다.")
            return

        # Bar chart using characters
        def draw_bar(val, max_val, color="green"):
            width = 40
            filled = int((val / max_val) * width) if max_val > 0 else 0
            bar = "█" * filled + "░" * (width - filled)
            percent = (val / max_val * 100) if max_val > 0 else 0
            return f"[{color}]{bar}[/{color}] {val} ({percent:.1f}%)"

        console.print(Panel(f"[bold]전체 통계 (총 {total}개 파일)[/bold]", style="magenta"))
        
        grid = Table.grid(padding=1)
        grid.add_column(style="bold", justify="right")
        grid.add_column()
        
        grid.add_row("인덱싱 완료", draw_bar(stats['s0'], total))
        grid.add_row("메타데이터", draw_bar(stats['s1'], total, "cyan"))
        grid.add_row("챕터 분할", draw_bar(stats['s4'], total, "blue"))
        grid.add_row("화수 검증", draw_bar(stats['s2'], total, "blue"))
        grid.add_row("EPUB 완성", draw_bar(stats['s5'], total, "green"))
        grid.add_row("오류 발생", draw_bar(stats['errors'], total, "red"))
        
        console.print(grid)
        input("\n엔터키를 누르면 돌아갑니다.")
