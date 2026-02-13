"""Stage 1: 메타데이터 수집

Gemini로 파일명 분석 → Perplexity로 웹 검색 → DB 저장
"""

import json
import time
from typing import List, Dict, Any, Optional
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.db.schema import Database
from novel_total_processor.ai.gemini_client import GeminiClient, NovelMetadata
from novel_total_processor.ai.perplexity_client import PerplexityClient
from novel_total_processor.config.loader import get_config
from novel_total_processor.utils.text_cleaner import clean_search_title, extract_episode_range_numeric

logger = get_logger(__name__)


class MetadataCollector:
    """메타데이터 수집기 (Stage 1)"""
    
    def __init__(self, db: Database):
        """
        Args:
            db: Database 인스턴스
        """
        self.db = db
        self.config = get_config()
        self.gemini = GeminiClient()
        self.perplexity = PerplexityClient()
        logger.info("MetadataCollector initialized")
    
    def _check_metadata_sufficient(self, metadata: Optional[NovelMetadata]) -> bool:
        """메타데이터가 최소 성공 기준을 만족하는지 확인
        
        최소 성공 기준: title + author + genre 중 2개 이상 존재
        
        Args:
            metadata: 검증할 메타데이터
        
        Returns:
            충분한 정보가 있으면 True, 아니면 False
        """
        if not metadata:
            return False
        
        # title은 항상 있다고 가정 (파일명에서 최소한 추출)
        # author, genre 중 최소 1개 이상 있어야 함
        has_title = True  # 파일명에서 최소한 제목은 추출됨
        has_author = bool(metadata.author and metadata.author.strip() and "Unknown" not in metadata.author)
        has_genre = bool(metadata.genre and metadata.genre.strip() and "Unknown" not in metadata.genre)
        
        # title + (author or genre) 조합이면 충분
        count = sum([has_title, has_author, has_genre])
        
        if count >= 2:
            return True
        
        logger.debug(f"   Insufficient metadata: author={has_author}, genre={has_genre}")
        return False
    
    def _merge_metadata(self, base: NovelMetadata, extra: Dict[str, Any]) -> NovelMetadata:
        """메타데이터 병합 (개선된 로직)
        
        병합 우선순위:
        1. 더 큰 episode_range 값 우선
        2. 더 최신 last_updated 값 우선
        3. 플랫폼 우선순위 (노벨피아, 네이버 시리즈, 리디, 네이버 웹소설, 카카오, 문피아, 조아라)
        
        Args:
            base: 기본 메타데이터 (Gemini 결과)
            extra: 추가 정보 (Perplexity 결과)
        
        Returns:
            병합된 메타데이터
        """
        # 플랫폼 우선순위 정의
        priority_platforms = [
            "노벨피아",
            "네이버 시리즈",
            "리디",
            "네이버 웹소설",
            "카카오",
            "문피아",
            "조아라"
        ]
        
        def get_platform_priority(platform: Optional[str]) -> int:
            """플랫폼 우선순위 점수 반환 (낮을수록 우선)"""
            if not platform:
                return 999
            for i, p in enumerate(priority_platforms):
                if p in platform:
                    return i
            return 900  # 기타 플랫폼
        
        def is_newer(d1: Optional[str], d2: Optional[str]) -> bool:
            """날짜 비교 (d1이 d2보다 최신이면 True)"""
            if not d1:
                return False
            if not d2:
                return True
            return d1 > d2
        
        # 에피소드 범위 비교
        base_ep_num = extract_episode_range_numeric(base.episode_range)
        extra_ep_num = extract_episode_range_numeric(extra.get("episode_range"))
        
        # 플랫폼 우선순위 비교
        base_priority = get_platform_priority(base.platform)
        extra_priority = get_platform_priority(extra.get("platform"))
        
        # 날짜 비교
        extra_is_newer = is_newer(extra.get("last_updated"), base.last_updated)
        
        # 병합 로직
        logger.info("   [Merge Decision]")
        
        # 제목: Perplexity가 우선순위 플랫폼이거나 더 최신일 경우 채택
        if extra.get("title"):
            if extra_priority < base_priority or extra_is_newer or (base.title and base.title.startswith("#")):
                logger.info(f"     → Title: Using Perplexity result (priority or newer)")
                base.title = extra["title"]
        
        # 작가: 없거나 Perplexity가 우선일 경우
        if extra.get("author"):
            if not base.author or extra_priority < base_priority or extra_is_newer:
                if base.author != extra["author"]:
                    logger.info(f"     → Author: '{base.author}' → '{extra['author']}' (priority or newer)")
                base.author = extra["author"]
        
        # 장르: 병합 (통합)
        if extra.get("genre"):
            if base.genre and base.genre != extra["genre"]:
                genres = {g.strip() for g in (base.genre + "," + extra["genre"]).split(",") if g.strip()}
                merged_genre = ", ".join(sorted(genres))
                logger.info(f"     → Genre: Merged '{base.genre}' + '{extra['genre']}' = '{merged_genre}'")
                base.genre = merged_genre
            elif not base.genre:
                base.genre = extra["genre"]
        
        # 상태: '완결'은 무조건 우선, 그 외는 최신 정보 우선
        if extra.get("status"):
            if "완결" in str(extra["status"]) or "완결" in str(base.status):
                base.status = "완결"
                logger.info(f"     → Status: '완결' (prioritized)")
            elif not base.status or extra_is_newer:
                base.status = extra["status"]
        
        # 에피소드 범위: 더 큰 값 우선, 같으면 최신 정보 우선
        if extra.get("episode_range"):
            if base_ep_num and extra_ep_num:
                if extra_ep_num > base_ep_num:
                    logger.info(f"     → Episode Range: {base.episode_range} → {extra['episode_range']} (larger)")
                    base.episode_range = extra["episode_range"]
                elif extra_ep_num == base_ep_num and extra_is_newer:
                    logger.info(f"     → Episode Range: {base.episode_range} → {extra['episode_range']} (same, but newer)")
                    base.episode_range = extra["episode_range"]
            elif not base.episode_range or extra_is_newer:
                base.episode_range = extra["episode_range"]
        
        # 날짜: 최신 정보 사용
        if extra_is_newer:
            logger.info(f"     → Last Updated: {base.last_updated} → {extra['last_updated']} (newer)")
            base.last_updated = extra["last_updated"]
        
        # 플랫폼: 우선순위가 높으면 교체
        if extra_priority < base_priority:
            logger.info(f"     → Platform: '{base.platform}' → '{extra['platform']}' (higher priority)")
            base.platform = extra["platform"]
        
        # 평점: 더 높은 평점 우선, 거의 같으면 최신 정보
        extra_rating = extra.get("rating")
        if extra_rating and extra_rating > 0:
            if not base.rating or extra_rating > base.rating:
                logger.info(f"     → Rating: {base.rating} → {extra_rating} (higher)")
                base.rating = extra_rating
            elif extra_is_newer and abs(extra_rating - base.rating) < 0.1:
                base.rating = extra_rating
        
        # 표지: 우선순위 플랫폼이거나 최신일 경우
        if extra.get("cover_url"):
            if not base.cover_url or extra_priority < base_priority or extra_is_newer:
                logger.info(f"     → Cover: Using Perplexity result")
                base.cover_url = extra["cover_url"]
        
        # 태그: 병합 및 성인물 판별
        if extra.get("tags"):
            all_tags = set(base.tags or []) | set(extra["tags"])
            
            # 성인물 판별
            adult_keywords = ["성인", "19금", "야겜", "R19", "노블레스", "성인물"]
            is_adult = any(kw in str(all_tags) for kw in adult_keywords)
            if is_adult:
                if not base.genre:
                    base.genre = "성인물"
                elif "성인물" not in base.genre:
                    base.genre = "성인물, " + base.genre
            
            merged_tags_count = len(all_tags)
            logger.info(f"     → Tags: Merged ({merged_tags_count} total tags)")
            base.tags = list(all_tags)[:15]
        
        # 공식 URL: 없으면 추가
        if extra.get("source_url") and not base.official_url:
            logger.info(f"     → Official URL: {extra['source_url']}")
            base.official_url = extra["source_url"]
        
        return base
    
    def get_pending_files(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Stage 1 대기 중인 파일 조회
        
        Args:
            limit: 최대 파일 수
        
        Returns:
            파일 정보 리스트 [{"id": int, "filename": str, "hash": str}, ...]
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        query = """
            SELECT f.id, f.file_name, f.file_hash
            FROM files f
            JOIN processing_state ps ON f.id = ps.file_id
            WHERE ps.stage0_indexed = 1 AND ps.stage1_meta = 0
            AND f.is_duplicate = 0
            ORDER BY f.id ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        files = [
            {"id": row[0], "filename": row[1], "hash": row[2]}
            for row in rows
        ]
        
        logger.info(f"Found {len(files)} files pending for Stage 1")
        return files
    
    def process_file(self, file_id: int, filename: str, file_hash: str) -> bool:
        """단일 파일 처리
        
        Args:
            file_id: 파일 ID
            filename: 파일명
            file_hash: 파일 해시
        
        Returns:
            성공 여부
        """
        try:
            # 1. Gemini로 메타데이터 추출 (최대 3회 재시도)
            metadata = None
            for attempt in range(1, 4):
                logger.info(f"   [AI 1/2] Gemini searching (Attempt {attempt}/3): {filename}")
                metadata = self.gemini.extract_metadata_from_filename(filename, file_hash)
                
                # 충분한 정보를 얻었는지 확인
                if self._check_metadata_sufficient(metadata):
                    logger.info("   ✅ Gemini search successful (sufficient info found)")
                    logger.info(f"      - Title: {metadata.title}")
                    logger.info(f"      - Author: {metadata.author}")
                    logger.info(f"      - Genre: {metadata.genre}")
                    logger.info(f"      - Rating: {metadata.rating}")
                    logger.info(f"      - Status: {metadata.status}")
                    logger.info(f"      - Tags: {', '.join(metadata.tags) if metadata.tags else '[]'}")
                    if metadata.official_url:
                        logger.info(f"      - Official URL: {metadata.official_url}")
                    break
                else:
                    logger.warning(f"   ⚠️ Gemini result insufficient (missing author or genre). {'Retrying with variant query...' if attempt < 3 else 'Giving up.'}")
                    if attempt < 3:
                        time.sleep(1)
            
            # 2. Perplexity로 보조 검색 (최대 3회 재시도)
            extra_info = None
            if self.perplexity.enabled and metadata and metadata.title:
                # 정리된 제목 사용
                search_title = clean_search_title(metadata.title)
                
                for attempt in range(1, 4):
                    logger.info(f"   [AI 2/2] Perplexity searching (Attempt {attempt}/3): {search_title}")
                    extra_info = self.perplexity.search_novel_info(search_title, metadata.author)
                    
                    # 제목 외에 다른 유의미한 정보가 있는지 확인
                    if extra_info and (extra_info.get("author") or extra_info.get("genre") or extra_info.get("rating")):
                        logger.info("   ✅ Perplexity search successful (info found)")
                        break
                    else:
                        logger.warning(f"   ⚠️ Perplexity result insufficient. {'Retrying with variant query...' if attempt < 3 else 'Giving up.'}")
                        if attempt < 3:
                            time.sleep(1)
            
            # 3. 데이터 병합 (Merge) - 고도화 버전
            if extra_info:
                metadata = self._merge_metadata(metadata, extra_info)
            
            # 3.5 구글 이미지 검색 보강 (표지가 없거나 저화질일 경우)
            if not metadata.cover_url or "novelpia_books_icon" in metadata.cover_url:
                logger.info(f"   🔍 Cover missing or low quality. Trying dedicated Google Image search...")
                # Gemini의 Google Search Grounding을 다시 활용하여 전용 이미지 쿼리 실행
                img_prompt = f'"{metadata.title}" {metadata.author or ""} 소설 공식 단행본 표지 이미지 고화질 direct image url format'
                img_metadata = self.gemini.extract_metadata_from_filename(img_prompt, f"img_{file_hash}")
                if img_metadata and img_metadata.cover_url and "novelpia_books_icon" not in img_metadata.cover_url:
                    metadata.cover_url = img_metadata.cover_url
                    logger.info(f"   ✅ Found better cover via Google search: {metadata.cover_url}")
            
            # 4. 표지 이미지 다운로드
            cover_path = None
            final_cover_url = metadata.cover_url
            if final_cover_url:
                logger.info(f"   🖼️ Downloading cover: {final_cover_url}")
                cover_path = self.perplexity.download_cover(final_cover_url, file_id)

            # 5. 최종 병합 결과 요약 출력
            logger.info(f"   [Final Merged Result]")
            logger.info(f"     • Title: {metadata.title}")
            logger.info(f"     • Author: {metadata.author}")
            logger.info(f"     • Genre: {metadata.genre}")
            logger.info(f"     • Rating: {metadata.rating}")
            logger.info(f"     • Platform: {metadata.platform}")
            logger.info(f"     • Updated: {metadata.last_updated}")
            logger.info(f"     • Tags: {', '.join(metadata.tags) if metadata.tags else '[]'}")
            logger.info(f"     • Status: {metadata.status}")
            if metadata.official_url:
                logger.info(f"     • Official URL: {metadata.official_url}")
            logger.info(f"     • Cover: {'[Success]' if cover_path else '[No/Failed]'}")
            
            # M-46: 파일명 힌트 강제 동기화 (AI가 놓쳤을 경우 대비)
            self._apply_filename_hints(metadata, filename)
            
            # 6. DB 저장
            self._save_to_db(file_id, metadata, extra_info, cover_path)
            
            logger.debug(f"✅ Processed: {filename}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")
            self._mark_error(file_id, str(e))
            return False
    
    def _apply_filename_hints(self, metadata: NovelMetadata, filename: str) -> None:
        """파일명에서 화수 힌트 등을 추출하여 메타데이터 보강 (M-46)"""
        import re
        # (1~321) 또는 (321) 등에서 화수 추출
        hint_nums = re.findall(r'\((\d+~\d+)\)', filename)
        hint_range = None
        if not hint_nums:
            hint_nums = re.findall(r'\((\d+)\)', filename)
            if hint_nums: hint_range = f"1~{hint_nums[0]}화"
        else:
            hint_range = f"{hint_nums[0]}화"
            
        if hint_range:
            # 기존 정보가 부실하거나 'Unknown'이면 덮어씀
            if not metadata.episode_range or "Unknown" in str(metadata.episode_range):
                metadata.episode_range = hint_range
                logger.info(f"   ✨ [Hint Apply] 파일명에서 화수 정보 추출: {hint_range}")
        
        # Unknown 문자열 제거 (작가, 장르 등)
        if metadata.author and "Unknown" in metadata.author: metadata.author = None
        if metadata.genre and "Unknown" in metadata.genre: metadata.genre = None
        if metadata.status and "Unknown" in metadata.status: metadata.status = None

    def _save_to_db(
        self,
        file_id: int,
        metadata: NovelMetadata,
        extra_info: Optional[Dict[str, Any]],
        cover_path: Optional[str] = None
    ) -> None:
        """DB에 저장
        
        Args:
            file_id: 파일 ID
            metadata: Gemini 메타데이터
            extra_info: Perplexity 추가 정보
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # novels 테이블 삽입/업데이트
        cursor.execute("""
            INSERT INTO novels (title, author, genre, tags, status, episode_range, rating, cover_path, platform, last_updated, official_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata.title,
            metadata.author,
            metadata.genre,
            ", ".join(metadata.tags) if metadata.tags else None,
            metadata.status,
            metadata.episode_range,
            metadata.rating,
            cover_path,
            metadata.platform,
            metadata.last_updated,
            metadata.official_url
        ))
        
        novel_id = cursor.lastrowid
        
        # 파일 테이블에 novel_id 연결
        cursor.execute("UPDATE files SET novel_id = ? WHERE id = ?", (novel_id, file_id))
        
        # novel_extra 테이블 (Perplexity 정보)
        if extra_info:
            cursor.execute("""
                INSERT INTO novel_extra (novel_id, source_url)
                VALUES (?, ?)
            """, (
                novel_id,
                extra_info.get("source_url")
            ))
        
        # processing_state 업데이트
        cursor.execute("""
            UPDATE processing_state
            SET stage1_meta = 1, last_stage = 'stage1', updated_at = datetime('now','localtime')
            WHERE file_id = ?
        """, (file_id,))
        
        conn.commit()
    
    def _mark_error(self, file_id: int, error_msg: str) -> None:
        """에러 기록
        
        Args:
            file_id: 파일 ID
            error_msg: 에러 메시지
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE processing_state
            SET last_error = ?, last_stage = 'stage1', updated_at = datetime('now','localtime')
            WHERE file_id = ?
        """, (error_msg, file_id))
        
        conn.commit()
    
    def run(self, limit: Optional[int] = None, batch_size: int = 10) -> Dict[str, int]:
        """Stage 1 실행
        
        Args:
            limit: 처리할 최대 파일 수
            batch_size: 배치 크기
        
        Returns:
            {"total": int, "success": int, "failed": int}
        """
        logger.info("=" * 50)
        logger.info("Stage 1: Metadata Collection")
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
            logger.info(f"[{i+1}/{len(files)}] {file['filename']}")
            
            if self.process_file(file["id"], file["filename"], file["hash"]):
                success_count += 1
            else:
                failed_count += 1
        
        logger.info("=" * 50)
        logger.info(f"✅ Stage 1 Complete: {success_count} success, {failed_count} failed")
        logger.info("=" * 50)
        
        return {
            "total": len(files),
            "success": success_count,
            "failed": failed_count
        }
