"""Stage 1: 메타데이터 수집

Gemini로 파일명 분석 → Perplexity로 웹 검색 → DB 저장
"""

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
            # 1. Gemini로 메타데이터 추출
            logger.debug(f"Processing file {file_id}: {filename}")
            metadata = self.gemini.extract_metadata_from_filename(filename, file_hash)
            
            # 2. Perplexity로 추가 정보 검색 (선택적)
            extra_info = None
            if self.perplexity.enabled and metadata.title:
                extra_info = self.perplexity.search_novel_info(
                    metadata.title,
                    metadata.author
                )
            
            # 3. DB 저장
            self._save_to_db(file_id, metadata, extra_info)
            
            logger.debug(f"✅ Processed: {filename}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")
            self._mark_error(file_id, str(e))
            return False
    
    def _save_to_db(
        self,
        file_id: int,
        metadata: NovelMetadata,
        extra_info: Optional[Dict[str, Any]]
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
            INSERT INTO novels (title, author, genre, tags, status, episode_range, rating)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata.title,
            metadata.author,
            metadata.genre,
            str(metadata.tags) if metadata.tags else None,  # JSON 문자열로 저장
            metadata.status,
            metadata.episode_range,
            extra_info.get("rating") if extra_info else None
        ))
        
        novel_id = cursor.lastrowid
        
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
