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
                
                # 충분한 정보를 얻었는지 확인 (제목 외에 작가, 장르, 태그 중 하나라도 있는 경우)
                if metadata and metadata.title and (metadata.author or metadata.genre or metadata.tags):
                    logger.info("   ✅ Gemini search successful (info found)")
                    logger.info(f"      - Title: {metadata.title}")
                    logger.info(f"      - Author: {metadata.author}")
                    logger.info(f"      - Rating: {metadata.rating}")
                    logger.info(f"      - Status: {metadata.status}")
                    break
                else:
                    logger.warning(f"   ⚠️ Gemini result insufficient. {'Retrying...' if attempt < 3 else 'Giving up.'}")
                    if attempt < 3:
                        time.sleep(1)
            
            # 2. Perplexity로 보조 검색 (최대 3회 재시도)
            extra_info = None
            if self.perplexity.enabled and metadata.title:
                for attempt in range(1, 4):
                    logger.info(f"   [AI 2/2] Perplexity searching (Attempt {attempt}/3): {metadata.title}")
                    extra_info = self.perplexity.search_novel_info(metadata.title, metadata.author)
                    
                    # 제목 외에 다른 유의미한 정보가 있는지 확인
                    if extra_info and (extra_info.get("author") or extra_info.get("genre") or extra_info.get("rating")):
                        logger.info("   ✅ Perplexity search successful (info found)")
                        break
                    else:
                        logger.warning(f"   ⚠️ Perplexity result insufficient. {'Retrying...' if attempt < 3 else 'Giving up.'}")
                        if attempt < 3:
                            time.sleep(1)
            
            # 3. 데이터 병합 (Merge) - 고도화 버전
            # 원칙: 1) 우선순위 플랫폼 정보优先, 2) 날짜가 더 최신인 정보优先
            if extra_info:
                # 헬퍼: 날짜 비교
                def is_newer(d1: Optional[str], d2: Optional[str]) -> bool:
                    if not d1: return False
                    if not d2: return True
                    # YYYY-MM-DD 포맷 가정
                    return d1 > d2

                # 헬퍼: 우선순위 사이트 여부
                priority_sites = ["노벨피아", "문피아", "조아라", "리디", "카카오", "네이버", "블라이스", "원스토리"]
                def has_priority(p: Optional[str]) -> bool:
                    if not p: return False
                    return any(s in p for s in priority_sites)

                # 병합 결정 로직 (Base: Gemini, Extra: Perplexity)
                p_newer = is_newer(extra_info.get("last_updated"), metadata.last_updated)
                p_priority = has_priority(extra_info.get("platform"))
                g_priority = has_priority(metadata.platform)

                # 0) 제목: Perplexity가 공식 사이트(우선순위) 제목을 찾았거나 더 최신일 경우 채택
                if extra_info.get("title") and (p_priority or p_newer or metadata.title.startswith("#")):
                    metadata.title = extra_info["title"]

                # 1) 작가, 장르: Gemini가 못 찾았거나 Perplexity가 우선순위/최신일 경우
                if extra_info.get("author") and (not metadata.author or p_priority or p_newer):
                    metadata.author = extra_info["author"]
                
                # M-42: 장르 병합 (하나만 택하지 않고 통합)
                if extra_info.get("genre"):
                    if metadata.genre and metadata.genre != extra_info["genre"]:
                        genres = {g.strip() for g in (metadata.genre + "," + extra_info["genre"]).split(",") if g.strip()}
                        metadata.genre = ", ".join(sorted(genres))
                    else:
                        metadata.genre = extra_info["genre"]

                # 2) 상태, 화수: 최신 정보(날짜)가 가장 중요하되, '완결'은 무조건 우선
                p_status = extra_info.get("status")
                if p_status:
                    if "완결" in str(p_status) or "완결" in str(metadata.status):
                        metadata.status = "완결"
                    elif not metadata.status or p_newer:
                        metadata.status = p_status
                
                if extra_info.get("episode_range") and (not metadata.episode_range or p_newer):
                    metadata.episode_range = extra_info["episode_range"]
                
                # 3) 날짜 및 플랫폼 업데이트
                if p_newer:
                    metadata.last_updated = extra_info["last_updated"]
                if p_priority:
                    metadata.platform = extra_info["platform"]

                # 4) 별점: Perplexity 것이 유효(0.0 아님)하고 최신이거나 Gemini가 없을 때
                p_rating = extra_info.get("rating")
                if p_rating and p_rating > 0 and (not metadata.rating or p_newer):
                    metadata.rating = p_rating

                # 5) 표지: 최신이거나 우선순위 사이트 것 우선
                if extra_info.get("cover_url") and (not metadata.cover_url or p_priority or p_newer):
                    metadata.cover_url = extra_info["cover_url"]

                # 6) 태그: 병합 및 성인물 판별 (M-42)
                if extra_info.get("tags"):
                    all_tags = set(metadata.tags or []) | set(extra_info["tags"])
                    
                    # 성인물 판별 키워드
                    adult_keywords = ["성인", "19금", "야겜", "R19", "노블레스", "성인물"]
                    is_adult = any(kw in str(all_tags) for kw in adult_keywords)
                    if is_adult:
                        if not metadata.genre: metadata.genre = "성인물"
                        elif "성인물" not in metadata.genre:
                            metadata.genre = "성인물, " + metadata.genre
                            
                    metadata.tags = list(all_tags)[:15] # 태그 수 약간 확장

                # 7) 공식 URL 병합 (M-49)
                if extra_info.get("source_url") and not metadata.official_url:
                    metadata.official_url = extra_info["source_url"]

            # 3.5 구글 이미지 검색 보강 (표지가 없거나 저화질일 경우)
            if not metadata.cover_url or "novelpia_books_icon" in metadata.cover_url:
                logger.info(f"   🔍 Cover missing or low quality. Trying dedicated Google Image search...")
                # Gemini의 Google Search Grounding을 다시 활용하여 전용 이미지 쿼리 실행
                img_prompt = f'"{metadata.title}" {metadata.author or ""} 소설 공식 단행본 표지 이미지 고화질 direct image url format'
                img_metadata = self.gemini.extract_metadata_from_filename(img_prompt, f"img_{file_hash}")
                if img_metadata.cover_url and "novelpia_books_icon" not in img_metadata.cover_url:
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
            logger.info(f"     • Official URL: {metadata.official_url}")
            logger.info(f"     • Cover: {'[Success]' if cover_path else '[No/Failed]'}")
            
            # DB 정보 업데이트 (platform, last_updated 등은 novel_extra 또는 기존 테이블 확장 필요하나 현재는 로그 출력 위주)

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
