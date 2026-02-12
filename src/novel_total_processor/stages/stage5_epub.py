"""Stage 5: EPUB 생성

EbookLib 기반 EPUB2 생성, 메타데이터 삽입, 표지 추가, CSS 스타일링
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from ebooklib import epub
from PIL import Image
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.db.schema import Database
from novel_total_processor.config.loader import get_config

logger = get_logger(__name__)


class EPUBGenerator:
    """EPUB 생성기 (Stage 5)"""
    
    def __init__(self, db: Database):
        """
        Args:
            db: Database 인스턴스
        """
        self.db = db
        self.config = get_config()
        
        # 출력 디렉토리
        self.output_dir = Path(self.config.paths.output_folder)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # CSS 템플릿 로드
        self.css_template = self._load_css_template()
        
        logger.info("EPUBGenerator initialized")
    
    def _load_css_template(self) -> str:
        """CSS 템플릿 로드
        
        Returns:
            CSS 문자열
        """
        css_path = Path(self.config.epub.css_template)
        if css_path.exists():
            with open(css_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            logger.warning(f"CSS template not found: {css_path}, using default")
            return self._get_default_css()
    
    def _get_default_css(self) -> str:
        """기본 CSS 반환
        
        Returns:
            기본 CSS 문자열
        """
        return """
body {
    font-family: "Noto Sans KR", "Malgun Gothic", sans-serif;
    line-height: 1.8;
    margin: 2em;
}

h1 {
    font-size: 1.8em;
    margin-top: 1em;
    margin-bottom: 0.5em;
    text-align: center;
}

h2 {
    font-size: 1.5em;
    margin-top: 1em;
    margin-bottom: 0.5em;
}

p {
    text-indent: 1em;
    margin: 0.5em 0;
}

.chapter-title {
    font-size: 1.5em;
    font-weight: bold;
    text-align: center;
    margin: 2em 0 1em 0;
}
"""
    
    def get_pending_files(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Stage 5 대기 중인 파일 조회 (Stage 3 완료 파일)
        
        Args:
            limit: 최대 파일 수
        
        Returns:
            파일 정보 리스트
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        query = """
            SELECT f.id, f.file_path, f.file_name, f.file_hash, f.encoding,
                   n.id as novel_id, n.title, n.author, n.genre, n.tags, 
                   n.status, n.rating, n.cover_path
            FROM files f
            JOIN processing_state ps ON f.id = ps.file_id
            LEFT JOIN novels n ON f.id = n.id
            WHERE ps.stage3_rename = 1 AND ps.stage5_epub = 0
            AND f.is_duplicate = 0 AND f.file_ext = '.txt'
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        files = []
        for row in rows:
            files.append({
                "file_id": row[0],
                "file_path": row[1],
                "file_name": row[2],
                "file_hash": row[3],
                "encoding": row[4],
                "novel_id": row[5],
                "title": row[6],
                "author": row[7],
                "genre": row[8],
                "tags": row[9],
                "status": row[10],
                "rating": row[11],
                "cover_path": row[12]
            })
        
        logger.info(f"Found {len(files)} files pending for Stage 5")
        return files
    
    def create_epub(self, file_info: Dict[str, Any]) -> str:
        """EPUB 생성 (다중 챕터 지원) 또는 EPUB 보강
        
        Args:
            file_info: 파일 정보
        
        Returns:
            생성된/보강된 EPUB 파일 경로
        """
        import json
        
        file_path = Path(file_info["file_path"])
        
        # TXT vs EPUB 분기
        if file_path.suffix.lower() == '.epub':
            # D-2: EPUB 원본 보강
            logger.info("   -> EPUB 원본 보강 모드")
            return self._enhance_existing_epub(file_info)
        else:
            # D-1: TXT → EPUB (풀 생성)
            logger.info("   -> TXT → EPUB 생성 모드")
            return self._create_epub_from_txt(file_info)
    
    def _create_epub_from_txt(self, file_info: Dict[str, Any]) -> str:
        """TXT 파일로부터 EPUB 생성 (D-1)
        
        Args:
            file_info: 파일 정보
        
        Returns:
            생성된 EPUB 파일 경로
        """
        import json
        
        # EPUB 객체 생성
        book = epub.EpubBook()
        
        # 메타데이터 설정
        self._set_metadata(book, file_info)
        
        # 표지 추가
        if file_info.get("cover_path"):
            self._add_cover(book, file_info["cover_path"])
        
        # CSS 추가
        css = epub.EpubItem(
            uid="style",
            file_name="style.css",
            media_type="text/css",
            content=self.css_template
        )
        book.add_item(css)
        
        # Stage 4 캐시에서 챕터 정보 로드
        stage4_cache = Path("data/cache/chapter_split") / f"{file_info['file_hash']}.json"
        
        if stage4_cache.exists():
            # 다중 챕터 EPUB 생성
            logger.info("   -> Stage 4 결과 활용: 다중 챕터 EPUB 생성")
            
            # Stage 4 데이터 로드
            with open(stage4_cache, "r", encoding="utf-8") as f:
                stage4_data = json.load(f)
            
            chapters, toc_structure = self._create_multi_chapters_with_toc(
                book, file_info, stage4_data, css
            )
        else:
            # 단일 챕터 EPUB (Stage 4 미완료 시 fallback)
            logger.warning("   -> Stage 4 캐시 없음: 단일 챕터 EPUB 생성")
            content = self._read_text_file(file_info["file_path"], file_info["encoding"])
            chapter = self._create_single_chapter(content, file_info["title"])
            chapter.add_item(css)
            book.add_item(chapter)
            chapters = [chapter]
            toc_structure = chapters
        
        # D-3: 계층형 목차 설정
        book.toc = toc_structure
        
        # NCX 및 Nav 추가
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # Spine 설정
        book.spine = ['nav'] + chapters
        
        # EPUB 파일 저장
        output_path = self._get_output_path(file_info["title"])
        epub.write_epub(output_path, book)
        
        logger.info(f"✅ EPUB created: {output_path} ({len(chapters)} chapters)")
        return str(output_path)
    
    def _enhance_existing_epub(self, file_info: Dict[str, Any]) -> str:
        """기존 EPUB 파일 보강 (D-2)
        
        Args:
            file_info: 파일 정보
        
        Returns:
            보강된 EPUB 파일 경로
        """
        epub_path = file_info["file_path"]
        
        try:
            # 기존 EPUB 열기
            book = epub.read_epub(epub_path)
            logger.info(f"   -> 기존 EPUB 로드: {Path(epub_path).name}")
            
            enhanced = False
            
            # 1. 표지 확인 및 추가
            if not self._has_cover(book) and file_info.get("cover_path"):
                logger.info("   -> 표지 추가")
                self._add_cover(book, file_info["cover_path"])
                enhanced = True
            
            # 2. 메타데이터 확인 및 업데이트
            if not self._has_complete_metadata(book):
                logger.info("   -> 메타데이터 업데이트")
                self._set_metadata(book, file_info)
                enhanced = True
            
            # 3. 목차(NCX) 확인 및 생성
            if not self._has_toc(book):
                logger.info("   -> 목차 생성")
                self._generate_toc_from_xhtml(book)
                enhanced = True
            
            # 4. 챕터 구조 확인 (1개 xhtml에 전부 있는지)
            xhtml_count = sum(1 for item in book.get_items() if item.get_type() == 9)
            if xhtml_count == 1:
                logger.warning("   ⚠️  단일 xhtml 파일 감지 (분할 필요)")
                # TODO: 향후 구현 - 단일 xhtml을 챕터별로 분할
            
            if enhanced:
                # 보강된 EPUB 저장
                output_path = self._get_output_path(file_info["title"] + "_enhanced")
                epub.write_epub(output_path, book)
                logger.info(f"✅ EPUB enhanced: {output_path}")
                return str(output_path)
            else:
                logger.info("   -> 보강 불필요 (이미 완전함)")
                return epub_path
        
        except Exception as e:
            logger.error(f"EPUB 보강 실패: {e}")
            return epub_path
    
    def _create_multi_chapters_with_toc(
        self,
        book: epub.EpubBook,
        file_info: Dict[str, Any],
        stage4_data: Dict[str, Any],
        css: epub.EpubItem
    ) -> tuple:
        """다중 챕터 생성 + 계층형 목차 (D-3)
        
        Args:
            book: EpubBook 객체
            file_info: 파일 정보
            stage4_data: Stage 4 캐시 데이터
            css: CSS 아이템
        
        Returns:
            (챕터 리스트, 계층형 목차 구조)
        """
        from novel_total_processor.stages.splitter import Splitter
        
        patterns = stage4_data.get("patterns", {})
        chapter_pattern = patterns.get("chapter_pattern")
        subtitle_pattern = patterns.get("subtitle_pattern")
        
        if not chapter_pattern:
            raise ValueError("챕터 패턴이 없습니다")
        
        # Splitter로 챕터 분할
        splitter = Splitter()
        chapter_generator = splitter.split(
            file_info["file_path"],
            chapter_pattern,
            subtitle_pattern
        )
        
        # 챕터별 xhtml 생성 + 타입별 분류
        all_chapters = []
        chapters_by_type = {
            "본편": [],
            "외전": [],
            "에필로그": [],
            "작가의 말": [],
            "기타": []
        }
        
        for ch in chapter_generator:
            # HTML 생성
            html_content = f"""<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{ch.title}</title>
    <link rel="stylesheet" href="style.css" type="text/css"/>
</head>
<body>
    <h1 class="chapter-title">{ch.title}</h1>
"""
            
            if ch.subtitle:
                html_content += f'    <h2 class="chapter-subtitle">{ch.subtitle}</h2>\n'
            
            # 본문 (줄바꿈 → <p> 태그)
            for line in ch.body.splitlines():
                line = line.strip()
                if line:
                    html_content += f'    <p>{line}</p>\n'
            
            html_content += """</body>
</html>"""
            
            # EpubHtml 생성
            epub_chapter = epub.EpubHtml(
                title=ch.title,
                file_name=f"chapter_{ch.cid:04d}.xhtml",
                lang="ko"
            )
            epub_chapter.content = html_content
            epub_chapter.add_item(css)
            
            book.add_item(epub_chapter)
            all_chapters.append(epub_chapter)
            
            # 타입별 분류
            chapters_by_type[ch.chapter_type].append(epub_chapter)
        
        # D-3: 계층형 목차 생성
        toc_structure = []
        
        # 본편
        if chapters_by_type["본편"]:
            toc_structure.append(
                (epub.Section("본편"), chapters_by_type["본편"])
            )
        
        # 외전
        if chapters_by_type["외전"]:
            toc_structure.append(
                (epub.Section("외전"), chapters_by_type["외전"])
            )
        
        # 에필로그
        if chapters_by_type["에필로그"]:
            toc_structure.append(
                (epub.Section("에필로그"), chapters_by_type["에필로그"])
            )
        
        # 작가의 말
        if chapters_by_type["작가의 말"]:
            toc_structure.append(
                (epub.Section("작가의 말"), chapters_by_type["작가의 말"])
            )
        
        # 기타
        if chapters_by_type["기타"]:
            toc_structure.extend(chapters_by_type["기타"])
        
        logger.info(f"   ✅ {len(all_chapters)}개 챕터 생성 완료")
        logger.info(f"      본편: {len(chapters_by_type['본편'])}개, 외전: {len(chapters_by_type['외전'])}개, 에필로그: {len(chapters_by_type['에필로그'])}개")
        
        return all_chapters, toc_structure
    
    def _create_single_chapter(self, content: str, title: str) -> epub.EpubHtml:
        """단일 챕터 생성 (fallback용)
        
        Args:
            content: 텍스트 내용
            title: 챕터 제목
        
        Returns:
            EpubHtml 챕터
        """
        # HTML 변환 (단락 분리)
        paragraphs = content.split("\n")
        html_content = f"<h1>{title}</h1>\n"
        
        for para in paragraphs:
            para = para.strip()
            if para:
                html_content += f"<p>{para}</p>\n"
        
        # EpubHtml 생성
        chapter = epub.EpubHtml(
            title=title,
            file_name="chapter.xhtml",
            lang="ko"
        )
        chapter.content = html_content
        
        return chapter
    
    def _set_metadata(self, book: epub.EpubBook, file_info: Dict[str, Any]) -> None:
        """메타데이터 설정
        
        Args:
            book: EpubBook 객체
            file_info: 파일 정보
        """
        # 필수 메타데이터
        book.set_identifier(f"ntp-{file_info['novel_id']}")
        book.set_title(file_info["title"])
        book.set_language("ko")
        
        # 작가
        if file_info.get("author"):
            book.add_author(file_info["author"])
        
        # 장르
        if file_info.get("genre"):
            book.add_metadata("DC", "subject", file_info["genre"])
        
        # 태그
        if file_info.get("tags"):
            for tag in file_info["tags"].split(","):
                book.add_metadata("DC", "subject", tag.strip())
        
        # 출판사 (Novel Total Processor)
        book.add_metadata("DC", "publisher", "Novel Total Processor")
        
        # 생성 날짜
        book.add_metadata("DC", "date", datetime.now().strftime("%Y-%m-%d"))
    
    def _add_cover(self, book: epub.EpubBook, cover_path: str) -> None:
        """표지 추가
        
        Args:
            book: EpubBook 객체
            cover_path: 표지 이미지 경로
        """
        try:
            path = Path(cover_path)
            if not path.exists():
                logger.warning(f"Cover not found: {cover_path}")
                return
            
            with open(path, "rb") as f:
                cover_data = f.read()
            
            book.set_cover("cover.jpg", cover_data)
            logger.debug("Cover added")
        except Exception as e:
            logger.error(f"Failed to add cover: {e}")
    
    def _read_text_file(self, file_path: str, encoding: Optional[str]) -> str:
        """텍스트 파일 읽기
        
        Args:
            file_path: 파일 경로
            encoding: 인코딩
        
        Returns:
            텍스트 내용
        """
        if not encoding:
            encoding = "utf-8"
        
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            # Fallback: UTF-8 with errors ignored
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    
    def _create_chapter(self, content: str, title: str) -> epub.EpubHtml:
        """챕터 생성
        
        Args:
            content: 텍스트 내용
            title: 챕터 제목
        
        Returns:
            EpubHtml 챕터
        """
        # HTML 변환 (단락 분리)
        paragraphs = content.split("\n")
        html_content = f"<h1>{title}</h1>\n"
        
        for para in paragraphs:
            para = para.strip()
            if para:
                html_content += f"<p>{para}</p>\n"
        
        chapter = epub.EpubHtml(
            title=title,
            file_name="chapter_01.xhtml",
            lang="ko"
        )
        chapter.content = html_content
        
        return chapter
    
    def _get_output_path(self, title: str) -> Path:
        """출력 파일 경로 생성
        
        Args:
            title: 소설 제목
        
        Returns:
            EPUB 파일 경로
        """
        # 파일명 정리
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-"))
        safe_title = safe_title.strip()[:100]  # 길이 제한
        
        filename = f"{safe_title}.epub"
        return self.output_dir / filename
    
    def save_to_db(self, file_id: int, novel_id: int, epub_path: str) -> None:
        """DB에 저장
        
        Args:
            file_id: 파일 ID
            novel_id: 소설 ID
            epub_path: EPUB 파일 경로
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # novels 테이블 업데이트
        cursor.execute("""
            UPDATE novels
            SET epub_path = ?, chapter_count = 1, updated_at = datetime('now','localtime')
            WHERE id = ?
        """, (epub_path, novel_id))
        
        # processing_state 업데이트
        cursor.execute("""
            UPDATE processing_state
            SET stage5_epub = 1, last_stage = 'stage5', updated_at = datetime('now','localtime')
            WHERE file_id = ?
        """, (file_id,))
        
        conn.commit()
    
    def run(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Stage 5 실행
        
        Args:
            limit: 처리할 최대 파일 수
        
        Returns:
            {"total": int, "success": int, "failed": int}
        """
        logger.info("=" * 50)
        logger.info("Stage 5: EPUB Generation")
        logger.info("=" * 50)
        
        # 대기 파일 조회
        files = self.get_pending_files(limit)
        
        if not files:
            logger.warning("No files to process")
            return {"total": 0, "success": 0, "failed": 0}
        
        # 처리
        success_count = 0
        failed_count = 0
        
        for i, file_info in enumerate(files):
            logger.info(f"[{i+1}/{len(files)}] {file_info['title']}")
            
            try:
                epub_path = self.create_epub(file_info)
                self.save_to_db(file_info["file_id"], file_info["novel_id"], epub_path)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to create EPUB: {e}")
                failed_count += 1
        
        logger.info("=" * 50)
        logger.info(f"✅ Stage 5 Complete: {success_count} success, {failed_count} failed")
        logger.info("=" * 50)
        
        return {
            "total": len(files),
            "success": success_count,
            "failed": failed_count
        }
    
    # ========== EPUB 보강 헬퍼 메서드 (D-2) ==========
    
    def _has_cover(self, book: epub.EpubBook) -> bool:
        """표지 존재 여부 확인"""
        for item in book.get_items():
            if 'cover' in item.get_name().lower():
                return True
        return False
    
    def _has_complete_metadata(self, book: epub.EpubBook) -> bool:
        """메타데이터 완전성 확인"""
        has_title = bool(book.get_metadata('DC', 'title'))
        has_author = bool(book.get_metadata('DC', 'creator'))
        return has_title and has_author
    
    def _has_toc(self, book: epub.EpubBook) -> bool:
        """목차 존재 여부 확인"""
        return len(book.toc) > 0
    
    def _generate_toc_from_xhtml(self, book: epub.EpubBook) -> None:
        """xhtml 파일로부터 목차 생성"""
        toc = []
        for item in book.get_items():
            if item.get_type() == 9:  # XHTML
                # 제목 추출 (간단히 파일명 사용)
                title = item.get_name().replace('.xhtml', '').replace('_', ' ').title()
                toc.append(item)
        
        book.toc = tuple(toc)
        logger.debug(f"Generated TOC with {len(toc)} entries")

