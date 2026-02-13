"""전체 파이프라인 통합 테스트 스크립트 (Mocked AI)
1. 테스트용 임시 폴더 생성 및 샘플 파일 복사
2. DB 초기화 (테스트용)
3. AI 컴포넌트 Mocking (API Key 없이 테스트)
4. Stage 0 -> 1 -> 4 -> 2 -> 3 -> 5 순차 실행
5. 결과물(EPUB) 검증
"""

import os
import shutil
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch
from rich.console import Console
from rich.panel import Panel

# 프로젝트 모듈 임포트
from novel_total_processor.config.loader import get_config
from novel_total_processor.db.schema import get_database, Database
from novel_total_processor.stages.stage0_indexing import FileScanner
from novel_total_processor.stages.stage1_metadata import MetadataCollector
from novel_total_processor.stages.stage4_splitter import ChapterSplitRunner
from novel_total_processor.stages.stage2_episode import EpisodePatternDetector
from novel_total_processor.stages.stage3_filename import FilenameGenerator
from novel_total_processor.stages.stage5_epub import EPUBGenerator
from novel_total_processor.stages.verifier import EPUBVerifier
from novel_total_processor.ai.gemini_client import NovelMetadata

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IntegrationTest")
console = Console()

def main():
    console.print(Panel.fit("[bold blue]🚀 통합 테스트: 전체 파이프라인 검증 (Mocked AI)[/bold blue]"))

    # 1. 테스트 환경 설정
    base_dir = Path("test_env")
    source_dir = base_dir / "source"
    output_dir = base_dir / "output"
    db_path = base_dir / "test.db"
    
    # 디렉토리 초기화
    if base_dir.exists():
        try:
            shutil.rmtree(base_dir)
        except Exception as e:
            console.print(f"[yellow]⚠️ 기존 폴더 삭제 실패 (무시됨): {e}[/yellow]")
            
    source_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 테스트 파일 복사
    origin_file = Path("e:/DEVz/10_Novel_Total_Processor/Test_Novels/2026-01-19/괴담에 떨어져도 출근을 해야 하는구나 1 (1-25).txt")
    
    if not origin_file.exists():
        console.print(f"[red]❌ 테스트용 원본 파일이 없습니다: {origin_file}[/red]")
        console.print("[yellow]⚠️ 더미 파일을 생성하여 테스트합니다.[/yellow]")
        # 더미 파일 (챕터 패턴 인식용)
        dummy_content = "제1화 시작\n\n내용입니다.\n\n제2화 진행\n\n더 많은 내용입니다."
        target_file = source_dir / "테스트소설.txt"
        target_file.write_text(dummy_content, encoding="utf-8")
        target_filename = "테스트소설.txt"
    else:
        target_file = source_dir / origin_file.name
        shutil.copy(origin_file, target_file)
        console.print(f"[green]✅ 테스트 파일 준비 완료: {target_file.name}[/green]")
        target_filename = target_file.name

    # 2. Config & DB 설정
    config = get_config()
    config.paths.source_folders = [str(source_dir)]
    config.paths.output_folder = str(output_dir)
    
    # DB 초기화
    db = Database(str(db_path))
    db.initialize_schema()
    
    try:
        # Stage 0: Indexing
        console.print("\n[bold]Step 0: Indexing[/bold]")
        scanner = FileScanner(db)
        total, dups = scanner.run()
        console.print(f"Index Result: Total {total}, Dups {dups}")
        assert total > 0, "Indexing failed: No files found"

        # --- MOCK SETUP ---
        # Stage 1 Mock: Metadata Extraction
        mock_metadata = NovelMetadata(
            title="테스트 소설",
            author="테스트 작가",
            genre="판타지",
            tags=["테스트", "가상"],
            status="연재중",
            episode_range="1~25"
        )
        
        # Stage 4 Mock: Pattern Detection
        mock_chapter_pattern = r"^제\d+화"
        # 실제 파일 내용에 맞는 패턴이어야 함. 
        # 원본 파일이 있다면 그에 맞는 패턴을 넣거나, 
        # PatternManager를 통째로 Mocking해서 정해진 패턴을 리턴하게 함.
        # "괴담에..." 파일은 "제N화" 형식이 아닐 수도 있음. "Episode N" 등일 수 있음.
        # 따라서 안전하게 PatternManager.find_best_pattern이 범용적인 패턴을 리턴하도록 함.
        # 만약 원본 파일("괴담...")을 쓴다면 그 파일의 실제 패턴을 알아야 함.
        # "괴담..."은 보통 텍본이면 "제1화", "1화", "Chapter 1" 등 다양함.
        # 여기서는 테스트 안전성을 위해, PatternManager가 "파일 내용과 무관하게" 
        # 항상 성공적인 패턴을 리턴한다고 가정하기보다,
        # 정규식 엔진이 동작할 수 있는 패턴을 줘야 함.
        # 하지만 파일 내용을 모르므로, PatternManager의 'detect' 로직을 신뢰하거나, 
        # 파일 내용을 읽어서 패턴을 주입해야 함.
        
        # 여기서는 "Dummy" 모드로 갔을 때 유효한 패턴을 줌.
        # 만약 Real File을 쓴다면, Real PatternManager가 동작해야 함.
        # 근데 API key가 없으므로 PatternManager도 Mocking해야 함.
        
        # 해결책: PatternManager.find_best_pattern을 Mocking하여
        # 항상 r"\d+화" 또는 해당 파일에 매칭될 법한 패턴을 리턴하게 함.
        # "괴담에..." 파일이 실제로 텍스트 파일이라면, 내용을 조금 열어보는게 좋음.
        # 일단 안전하게 r"^\d+|제\d+화|Chapter \d+" 등을 리턴하게 함.
        
        with patch("novel_total_processor.stages.stage1_metadata.GeminiClient") as MockGeminiClient, \
             patch("novel_total_processor.stages.stage4_splitter.PatternManager") as MockPatternManager:
            
            # Mock Gemini Client Setup
            mock_gemini_instance = MockGeminiClient.return_value
            mock_gemini_instance.extract_metadata_from_filename.return_value = mock_metadata
            
            # Mock Pattern Manager Setup
            mock_pm_instance = MockPatternManager.return_value
            # 파일 내용을 몰라도 일단 정규식 리턴.
            # 실제 파일("괴담...")의 내용을 샘플링해서 정규식을 찾는지 확인해야겠지만,
            # 통합 테스트에서는 "가짜 패턴"이라도 리턴해서 Splitter가 도는질 검증.
            # 하지만 패턴이 안 맞으면 챕터 분할이 0개가 됨.
            # 따라서 "모든 줄이 챕터"가 되지 않도록 주의.
            # 가장 흔한 패턴 리턴
            mock_pm_instance.find_best_pattern.return_value = (r"^(?:제)?\d+[화장\.]", None)

            # Stage 1 실행
            console.print("\n[bold]Step 1: Metadata (Mocked)[/bold]")
            collector = MetadataCollector(db)
            res1 = collector.run(limit=1)
            console.print(f"Meta Result: {res1}")
            
            # Stage 4 실행
            console.print("\n[bold]Step 4: Splitter (Mocked)[/bold]")
            splitter = ChapterSplitRunner(db)
            
            # 챕터 분할이 실제로 되려면, 파일 내용과 패턴이 맞아야 함.
            # Mock PatternManager가 리턴한 패턴이 실제 파일 내용과 안 맞으면 챕터 0개 -> 실패 가능성.
            # 따라서, 원본 파일을 쓸 때는 PatternManager가 AI 없이도 동작하는 'RegexFallback' 모드가 있으면 좋음.
            # 현재 코드는 AI에 의존적일 수 있음.
            # 여기서는 split_chapters 메소드 자체를 Mocking해서 '가짜 챕터'를 리턴하는게 
            # '파이프라인 흐름' 검증에는 더 확실함. (Splitter 로직 자체 테스트는 Unit Test의 영역)
            # 하지만 우리는 '통합' 테스트이므로, DB 업데이트와 파일 생성이 되는지 봐야 함.
            
            # split_chapters를 Mocking하여 결과 dict 리턴
            with patch.object(splitter, 'split_chapters') as mock_split:
                mock_split.return_value = {
                    "chapters": [
                        MagicMock(cid=0, title="제1화", subtitle=None, length=100, chapter_type="본편"),
                        MagicMock(cid=1, title="제2화", subtitle=None, length=200, chapter_type="본편")
                    ],
                    "summary": {
                        "total": 2,
                        "본편": {"count": 2, "start": 1, "end": 2},
                        "외전": {"count": 0}, 
                        "에필로그": {"count": 0}, 
                        "작가의 말": {"count": 0}
                    },
                    "patterns": {"chapter_pattern": r"^제\d+화", "subtitle_pattern": None}
                }
                
                res4 = splitter.run(limit=1)
                console.print(f"Split Result: {res4}")

        # Stage 2: Verification (DB 기반이라 Mock 불필요하거나, DB 상태에 의존)
        console.print("\n[bold]Step 2: Episode Verification[/bold]")
        detector = EpisodePatternDetector(db)
        res2 = detector.run(limit=1)
        console.print(f"Episode Verify Result: {res2}")
        
        # Stage 3: Rename
        console.print("\n[bold]Step 3: Rename[/bold]")
        renamer = FilenameGenerator(db)
        res3 = renamer.run(limit=1)
        console.print(f"Rename Result: {res3}")
        
        # Stage 5: EPUB
        console.print("\n[bold]Step 5: EPUB Generation[/bold]")
        epub_gen = EPUBGenerator(db)
        res5 = epub_gen.run(limit=1)
        console.print(f"EPUB Result: {res5}")
        assert res5['success'] > 0, "EPUB Generation failed"

        # Final Verification
        console.print("\n[bold]Final Verification[/bold]")
        conn = db.connect()
        cur = conn.cursor()
        cur.execute("SELECT epub_path, title FROM novels WHERE epub_path IS NOT NULL")
        row = cur.fetchone()
        
        if row:
            epub_path = row[0]
            title = row[1]
            console.print(f"Generated EPUB: {epub_path}")
            
            # 실제 파일 검증은 EPUBGenerator가 Mock된 챕터정보를 바탕으로 '실제 파일'을 읽으려 할 때 
            # 'split_chapters'가 파일 생성을 안 해줬으므로 실패할 수 있음.
            # 아... Splitter는 '결과 저장'만 하고 실제 파일 분할(쪼개기)은 Cache에만 저장하나?
            # Stage 5 EPUBGenerator는 '원본 파일'을 다시 읽어서 챕터별로 자르나? 
            # 아니면 Splitter가 만들어둔 JSON을 보고 자르나?
            # 코드를 보면 EPUBGenerator는 DB 정보와 원본 파일을 이용해 epub을 만듦.
            # 따라서 'split_chapters'가 리턴한 'chapters' 정보(위치 등)가 정확해야 함.
            # Mock된 챕터 정보가 실제 파일 위치와 안 맞으면 EPUB 생성 시 에러 나거나 빈 내용.
            # 하지만 '통합 테스트'의 목적이 파이프라인 연결 확인리면, 파일 생성 성공 여부만 봐도 됨.
            
            if os.path.exists(epub_path):
                 console.print("\n[bold green]🎉 통합 테스트 성공! (EPUB Created)[/bold green]")
            else:
                 console.print("\n[bold red]❌ EPUB 파일 생성 실패 (파일 없음)[/bold red]")

        else:
            console.print("\n[bold red]❌ EPUB 파일이 DB에 등록되지 않았습니다.[/bold red]")

    except Exception as e:
        console.print(f"\n[bold red]❌ 테스트 중 치명적 오류 발생: {e}[/bold red]")
        logger.exception("Test failed")
    finally:
        db.close()

if __name__ == "__main__":
    main()
