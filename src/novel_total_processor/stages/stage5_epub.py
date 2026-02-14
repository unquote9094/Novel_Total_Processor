"""Stage 5: EPUB 생성

EbookLib 기반 EPUB2 생성, 메타데이터 삽입, 표지 추가, CSS 스타일링
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from ebooklib import epub
from PIL import Image
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.db.schema import Database
from novel_total_processor.config.loader import get_config
from novel_total_processor.stages.epub_templates import (
    create_chapter_page, create_volume_page, create_cover_html, get_css
)

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
                n.status, n.rating, n.cover_path, n.chapter_count, n.episode_range, n.reconciliation_log
            FROM files f
            JOIN processing_state ps ON f.id = ps.file_id
            LEFT JOIN novels n ON f.novel_id = n.id
            WHERE ps.stage3_rename = 1 AND ps.stage5_epub = 0
            AND f.is_duplicate = 0 AND f.file_ext IN ('.txt', '.epub')
            ORDER BY f.id ASC
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
                "cover_path": row[12],
                "chapter_count": row[13],
                "episode_range": row[14],
                "reconciliation_log": row[15]
            })
        
        logger.info(f"Found {len(files)} files pending for Stage 5")
        return files
    
    def create_epub(self, file_info: Dict[str, Any]) -> tuple:
        """EPUB 생성 (다중 챕터 지원) 또는 EPUB 보강
        
        Args:
            file_info: 파일 정보
        
        Returns:
            (epub_path, chapter_count) 튜플
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
        
        # EPUB 객체 생성 (EPUB 2.0.1 설정)
        book = epub.EpubBook()
        book.FOLDER_NAME = 'OEBPS' # 표준 폴더명 강제 (EbookLib 기본값 EPUB에서 변경)
        book.EPUB_VERSION = 2  # EPUB 2.0.1 강제 (OEBPS 구조 유지용)
        
        # 메타데이터 설정
        self._set_metadata(book, file_info)
        
        # 표지 추가 (이미지 파일 + XHTML 페이지)
        cover_image_item = None
        if file_info.get("cover_path"):
            cover_image_item = self._add_cover(book, file_info["cover_path"])
        
        # CSS 추가 (OEBPS/Styles/style.css)
        css = epub.EpubItem(
            uid="style",
            file_name="Styles/style.css",
            media_type="text/css",
            content=get_css()
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
            # 단일 챕터 EPUB (Fallback)
            logger.warning("   -> Stage 4 캐시 없음: 단일 챕터 EPUB 생성")
            content = self._read_text_file(file_info["file_path"], file_info["encoding"])
            chapter = self._create_single_chapter(content, file_info["title"])
            book.add_item(chapter)
            chapters = [chapter]
            toc_structure = chapters
        
        # 목차 설정
        book.toc = toc_structure
        
        # NCX (EPUB 2 필수)
        book.add_item(epub.EpubNcx())
        
        # Spine 설정 (Nav 제외, 커버 페이지가 있으면 맨 앞에)
        # ⚠️ EbookLib의 set_cover는 'linear="no"'로 설정하여 spine 맨 앞에 자동으로 안 들어갈 수 있음
        # 수동으로 spine을 구성함
        
        spine_items = []
        # 만약 별도의 커버 XHTML을 만들었다면 추가 (create_multi_chapters에서 처리됨?)
        # 여기서는 챕터 리스트만 추가
        spine_items.extend(chapters)
        
        book.spine = spine_items
        
        # Guide 설정 (표지, 시작 페이지 등)
        # cover_image_item이 있으면 guide에 추가됨 (ebooklib 자동 처리 아님, 수동 추가 필요)
        
        # EPUB 파일 저장
        output_path = self._get_output_path(file_info["file_name"])
        epub.write_epub(output_path, book, {})
        
        logger.info(f"✅ EPUB created: {output_path} ({len(chapters)} chapters)")
        return str(output_path), len(chapters)
    
    def _enhance_existing_epub(self, file_info: Dict[str, Any]) -> tuple:
        """기존 EPUB 파일 보강 (D-2)
        
        Args:
            file_info: 파일 정보
        
        Returns:
            (보강된 EPUB 파일 경로, 챕터 수)
        """
        epub_path = file_info["file_path"]
        
        try:
            # 기존 EPUB 열기
            book = epub.read_epub(epub_path)
            book.FOLDER_NAME = 'OEBPS' # 보강 시에도 폴더 구조 유지 강제
            book.EPUB_VERSION = 2     # EPUB2 버전 유지 강제
            logger.info(f"   -> 기존 EPUB 로드: {Path(epub_path).name}")
            
            # 챕터 수 계산 (M-32: Stage 4 로직과 동일하게 본문만 카운트)
            chapters = []
            spine_ids = [s[0] for s in book.spine if isinstance(s, tuple)]
            for item_id in spine_ids:
                item = book.get_item_with_id(item_id)
                if item and item.get_type() == 9:
                    name = item.get_name().lower()
                    if not any(x in name for x in ['cover', 'nav', 'toc', 'titlepage', 'metadata']):
                        chapters.append(item)
            chapter_count = len(chapters)
            
            enhanced = False
            
            # 1. 표지 업데이트 (M-33: 고화질 이미지 우선 비교)
            if file_info.get("cover_path"):
                new_cover_path = Path(file_info["cover_path"])
                if new_cover_path.exists():
                    should_update_cover = True
                    # 기존 표지 크기 확인
                    existing_cover = None
                    for item in book.get_items():
                        if 'cover' in item.get_name().lower():
                            existing_cover = item
                            break
                    
                    if existing_cover:
                        old_size = len(existing_cover.get_content())
                        new_size = new_cover_path.stat().st_size
                        if new_size < old_size * 0.8: # 새 이미지가 20% 이상 작으면 저화질로 간주하고 스킵
                            logger.info(f"   -> [Skip Cover] Existing cover is larger/better quality ({old_size} vs {new_size} bytes)")
                            should_update_cover = False
                    
                    if should_update_cover:
                        logger.info(f"   -> [Update Cover] Syncing latest cover: {new_cover_path.name}")
                        self._add_cover(book, str(new_cover_path))
                        enhanced = True
            
            # 2. 메타데이터 강제 업데이트 (M-33: reset_metadata 오류 수정)
            logger.info(f"   -> [Update Meta] Syncing latest metadata from AI search results...")
            self._set_metadata(book, file_info)
            enhanced = True
            
            # 3. 목차(NCX) 재생성 (번호 부여 포함)
            logger.info("   -> [Update TOC] Re-generating Table of Contents with proper indexing")
            self._generate_toc_from_spine(book)
            enhanced = True
            
            if enhanced:
                output_path = self._get_output_path(file_info["file_name"])
                epub.write_epub(output_path, book, {}) # {} 옵션으로 여분의 nav.xhtml 생성 방지 시도
                logger.info(f"✅ EPUB enhanced & saved: {output_path.name}")
                return str(output_path), chapter_count
            else:
                return epub_path, chapter_count
        
        except Exception as e:
            logger.error(f"EPUB 보강 실패: {e}")
            raise e # 상위 run()에서 failed_count를 올바르게 집계하도록 예외 던짐
    
    def _create_multi_chapters_with_toc(
        self,
        book: epub.EpubBook,
        file_info: Dict[str, Any],
        stage4_data: Dict[str, Any],
        css: epub.EpubItem
    ) -> tuple:
        """다중 챕터 생성 + 계층형 목차 (D-3)"""
        from novel_total_processor.stages.splitter import Splitter
        from novel_total_processor.stages.chapter import Chapter
        
        # Try to use chapters directly from Stage 4 cache
        chapters_data = stage4_data.get("chapters", [])
        
        if chapters_data:
            # Use chapters directly from Stage 4 (includes Advanced Pipeline results)
            logger.info(f"   -> Using {len(chapters_data)} chapters from Stage 4 cache")
            all_ch_objs = [
                Chapter(
                    cid=ch['cid'],
                    title=ch['title'],
                    subtitle=ch.get('subtitle', ''),
                    body=ch['body'],
                    length=ch.get('length', len(ch['body'])),
                    chapter_type=ch.get('chapter_type', '본편')
                )
                for ch in chapters_data
            ]
        else:
            # Fallback: Use pattern-based splitting (old behavior)
            logger.warning("   -> Stage 4 cache has no chapter data, falling back to pattern split")
            
            splitter = Splitter()
            patterns = stage4_data.get("patterns", {})
            pattern = patterns.get("chapter_pattern", r"^\d+화$") 
            subtitle_pattern = patterns.get("subtitle_pattern", None)

            all_ch_objs = list(splitter.split(
                file_info["file_path"],
                pattern,
                subtitle_pattern,
                encoding=file_info.get("encoding", "utf-8") or "utf-8"
            ))
        
        if not all_ch_objs:
             raise ValueError("챕터가 추출되지 않았습니다.")

        # 타입별 분류
        chapters_by_type = {}
        type_order = []
        
        for ch in all_ch_objs:
            if not ch.body or not ch.body.strip(): continue # 빈 챕터 제외
            
            if ch.chapter_type not in chapters_by_type:
                chapters_by_type[ch.chapter_type] = []
                type_order.append(ch.chapter_type)
            chapters_by_type[ch.chapter_type].append(ch)
            
        final_spine_items = []
        toc_structure = []
        all_chapters_count = 0
        
        # 표지 페이지 (Cover XHTML) - 만약 커버가 있으면
        if self._has_cover(book):
            cover_page = create_cover_html(file_name="Text/cover.xhtml", image_path="../Images/cover.jpg")
            book.add_item(cover_page)
            # 표지는 보통 spine 맨 앞
            final_spine_items.append(cover_page)
        
        # 타입별 순회
        for c_type in type_order:
            ch_list = chapters_by_type[c_type]
            if not ch_list: continue
            
            # 1. 볼륨(부) 타이틀 페이지 생성 (M-22: 단일 권 시 생략)
            needs_vol_page = len(type_order) > 1
            vol_filename = None
            
            if needs_vol_page:
                safe_type_name = "".join(x for x in c_type if x.isalnum())
                if not safe_type_name: safe_type_name = "vol"
                    
                vol_filename = f"Text/vol_{safe_type_name}.xhtml"
                vol_page = create_volume_page(c_type, vol_filename)
                book.add_item(vol_page)
                final_spine_items.append(vol_page)
            
            # 2. 챕터 페이지 생성
            vol_chapter_links = []
            
            for ch in ch_list:
                all_chapters_count += 1
                # M-23: 모든 챕터 제목 앞에 자동 넘버링 (001. 형식) 추가
                numbered_title = f"{all_chapters_count:03d}. {ch.title}"
                
                filename = f"Text/chapter_{ch.cid:04d}.xhtml"
                epub_ch = create_chapter_page(
                    title=numbered_title,
                    body=ch.body,
                    file_name=filename,
                    subtitle=ch.subtitle
                )
                book.add_item(epub_ch)
                final_spine_items.append(epub_ch)
                
                # TOC Link
                vol_chapter_links.append(epub.Link(filename, numbered_title, Path(filename).stem))
            
            # 3. TOC 구조 추가 (M-22: 다중 권일 때만 중첩 구조 사용)
            if needs_vol_page:
                vol_link = epub.Link(vol_filename, c_type, Path(vol_filename).stem)
                toc_structure.append((vol_link, vol_chapter_links))
            else:
                # 단일 권인 경우 챕터 리스트를 직접 TOC 루트에 추가
                toc_structure.extend(vol_chapter_links)
            
        return final_spine_items, toc_structure
    
    def _create_single_chapter(self, content: str, title: str) -> epub.EpubHtml:
        """단일 챕터 생성"""
        return create_chapter_page(
            title=title, 
            body=content, 
            file_name="Text/chapter_01.xhtml"
        )
    
    def _set_metadata(self, book: epub.EpubBook, file_info: Dict[str, Any]) -> None:
        """메타데이터 설정
        
        Args:
            book: EpubBook 객체
            file_info: 파일 정보
        """
        # M-33/34: 기존 메타데이터 초기화 (ebooklib 내부 구조 보호하며 DC 필드만 제거)
        dc_ns = 'http://purl.org/dc/elements/1.1/'
        if dc_ns in book.metadata:
            # 주요 필드만 선별적으로 제거하여 객체 안정성 유지
            for key in ['title', 'creator', 'subject', 'description', 'publisher', 'date', 'language']:
                if key in book.metadata[dc_ns]:
                    del book.metadata[dc_ns][key]
        
        book.set_identifier(f"ntp-{file_info['novel_id']}")
        book.set_title(file_info["title"])
        book.set_language("ko")
        
        # 1. 작가 (Creator) - 제목 다음으로 중요 (dc:creator)
        if file_info.get("author"):
            book.add_author(file_info["author"])
        
        # 2. 장르 (Subject 최상단 - dc:subject)
        if file_info.get("genre") and "Unknown" not in file_info["genre"]:
            book.add_metadata("DC", "subject", file_info["genre"])
        
        # 3. 화수 정보 (Subject 두 번째 - dc:subject)
        # M-46: 파일명 힌트가 있다면 최우선 적용
        hint_range = None
        hint_nums = re.findall(r'\((\d+~\d+)\)', file_info.get("file_name", ""))
        if not hint_nums:
            hint_nums = re.findall(r'\((\d+)\)', file_info.get("file_name", ""))
            if hint_nums: hint_range = f"1~{hint_nums[0]}화"
        else:
            hint_range = f"{hint_nums[0]}화"

        original_range = file_info.get("episode_range")
        chapter_count = file_info.get("chapter_count")
        
        reconciled_range = original_range
        if hint_range:
            reconciled_range = hint_range
        elif chapter_count and chapter_count > 0:
            reconciled_range = f"1~{chapter_count}화"
        
        if reconciled_range and "Unknown" not in reconciled_range:
            book.add_metadata("DC", "subject", reconciled_range)
            
            description = f"Episodes: {reconciled_range}"
            if file_info.get("reconciliation_log"):
                description += f"\n\n[Reconciliation Log]\n{file_info['reconciliation_log']}"
            book.add_metadata("DC", "description", description)

        # 4. 태그 (Subject 그 다음 - dc:subject)
        if file_info.get("tags"):
            tags_raw = file_info["tags"]
            tags_list = []
            if tags_raw.strip().startswith("["):
                try:
                    import json
                    tags_list = json.loads(tags_raw)
                except:
                    tags_list = [t.strip() for t in tags_raw.split(",")]
            else:
                tags_list = [t.strip() for t in tags_raw.split(",")]
                
            for tag in tags_list:
                if tag and "Unknown" not in tag:
                    book.add_metadata("DC", "subject", tag)
                    
        # M-47: dc:publisher, dc:date 항목은 실제 정보가 아니므로 제거함
    
    
    def _add_cover(self, book: epub.EpubBook, cover_path: str) -> epub.EpubItem:
        """표지 이미지 추가 (OEBPS/Images/cover.jpg)"""
        try:
            path = Path(cover_path)
            if not path.exists():
                return None
            
            with open(path, "rb") as f:
                cover_data = f.read()
            
            # Images 폴더에 저장
            # set_cover는 내부적으로 item을 만들고, guide에 추가함.
            # 하지만 우리는 파일명을 제어하고 싶음.
            book.set_cover("Images/cover.jpg", cover_data)
            
            # item 반환 (필요시)
            return None
        except Exception as e:
            logger.error(f"Failed to add cover: {e}")
            return None
    
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
    
    def _get_output_path(self, file_name: str) -> Path:
        """출력 파일 경로 생성
        
        Args:
            file_name: 표준화된 파일명 (확장자 제외)
        
        Returns:
            EPUB 파일 경로
        """
        # 파일명 정리: 공백, 점, 물결, 괄호 등 허용
        # Windows 금지 문자: <>:"/\|?*
        forbidden = '<>:"/\\|?*'
        safe_title = "".join(c for c in file_name if c not in forbidden)
        safe_title = safe_title.strip()[:150]  # 길이 제한 약간 완화
        
        # 확장자 중복 방지 (이미 .epub이면 추가 안함)
        if not safe_title.lower().endswith(".epub"):
            filename = f"{safe_title}.epub"
        else:
            filename = safe_title
            
        return self.output_dir / filename
    
    def save_to_db(self, file_id: int, novel_id: int, epub_path: str, chapter_count: int) -> None:
        """DB에 저장
        
        Args:
            file_id: 파일 ID
            novel_id: 소설 ID
            epub_path: EPUB 파일 경로
            chapter_count: 챕터 수
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # novels 테이블 업데이트
        cursor.execute("""
            UPDATE novels
            SET epub_path = ?, chapter_count = ?
            WHERE id = ?
        """, (epub_path, chapter_count, novel_id))
        
        # processing_state 업데이트
        cursor.execute("""
            UPDATE processing_state
            SET stage5_epub = 1, last_stage = 'stage5'
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
        
        for i, file in enumerate(files):
            title = file.get("title", "Unknown")
            file_path_obj = Path(file["file_path"])
            logger.info(f"[{i+1}/{len(files)}] {title}")
            
            if not file_path_obj.exists():
                logger.warning(f"   ⚠️  파일이 디스크에 없습니다. 스킵합니다: {file_path_obj}")
                failed_count += 1
                continue
                
            try:
                # 텍스트 파일이면 EPUB 생성, EPUB이면 메타데이터 보강
                epub_path, chapter_count = self.create_epub(file)
                self.save_to_db(file["file_id"], file["novel_id"], epub_path, chapter_count)
                logger.info(f"   ✅ [Finish] Result saved to completion folder: {Path(epub_path).name}")
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
    
    def _generate_toc_from_spine(self, book: epub.EpubBook) -> None:
        """Spine 구조로부터 정제된 목차 생성 (M-32: 넘버링 포함)"""
        toc = []
        cid = 1
        
        spine_ids = [s[0] for s in book.spine if isinstance(s, tuple)]
        for item_id in spine_ids:
            item = book.get_item_with_id(item_id)
            if item and item.get_type() == 9:
                name = item.get_name().lower()
                if any(x in name for x in ['cover', 'nav', 'toc', 'titlepage', 'metadata']):
                    continue
                
                # 제목 추출 및 무조건 넘버링 부여 (M-34: 정합성 보장)
                content = item.get_content().decode('utf-8', errors='ignore')
                title = item.get_name()
                match = re.search(r'<(?:h1|h2|title)[^>]*>(.*?)</(?:h1|h2|title)>', content, re.IGNORECASE | re.DOTALL)
                if match:
                    title = re.sub(r'<[^>]*>', '', match.group(1)).strip()
                
                # 기존에 숫자가 있든 없든 [N] 형식으로 통일하여 업데이트
                display_title = f"[{cid}] {title}"
                    
                toc.append(epub.Link(item.get_name(), display_title, item.id))
                cid += 1
        
        book.toc = tuple(toc)
        
        # M-36/39: 중복 방지 및 EPUB2 표준 준수 (nav.xhtml 제외)
        to_remove = []
        for item in book.get_items():
            if isinstance(item, (epub.EpubNcx, epub.EpubNav)) or \
               ('toc.ncx' in item.get_name().lower()) or \
               ('nav.xhtml' in item.get_name().lower()):
                to_remove.append(item)
        
        for item in to_remove:
            if item in book.items:
                book.items.remove(item)
        
        # EPUB2 필수 요소인 NCX만 추가
        book.add_item(epub.EpubNcx())
        logger.debug(f"Generated clean TOC with {len(toc)} entries (cleaned duplicates, pure EPUB2)")

