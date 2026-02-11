"""Stage 6: 통합 및 배치 처리

일일 배치 로그, 통계, 중복 정리
"""

from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.db.schema import Database

logger = get_logger(__name__)


class BatchProcessor:
    """배치 처리기 (Stage 6)"""
    
    def __init__(self, db: Database):
        """
        Args:
            db: Database 인스턴스
        """
        self.db = db
        logger.info("BatchProcessor initialized")
    
    def create_batch_log(
        self,
        batch_name: str,
        batch_type: str,
        total_files: int,
        processed: int,
        success: int,
        failed: int,
        started_at: str,
        finished_at: str,
        duration_sec: int
    ) -> int:
        """배치 로그 생성
        
        Args:
            batch_name: 배치 이름 (예: 'daily_2026-02-12')
            batch_type: 배치 타입 ('full' / 'daily')
            total_files: 총 파일 수
            processed: 처리된 파일 수
            success: 성공 수
            failed: 실패 수
            started_at: 시작 시간
            finished_at: 종료 시간
            duration_sec: 소요 시간 (초)
        
        Returns:
            배치 로그 ID
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO batch_logs 
            (batch_name, batch_type, total_files, processed, success, failed, 
             started_at, finished_at, duration_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            batch_name, batch_type, total_files, processed, success, failed,
            started_at, finished_at, duration_sec
        ))
        
        batch_id = cursor.lastrowid
        conn.commit()
        
        logger.info(f"✅ Batch log created: {batch_name} (ID: {batch_id})")
        return batch_id
    
    def get_statistics(self) -> Dict[str, Any]:
        """전체 통계 조회
        
        Returns:
            통계 딕셔너리
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # 파일 통계
        cursor.execute("""
            SELECT 
                COUNT(*) as total_files,
                SUM(CASE WHEN is_duplicate = 1 THEN 1 ELSE 0 END) as duplicates,
                SUM(file_size) as total_size
            FROM files
        """)
        file_stats = cursor.fetchone()
        
        # 처리 상태 통계
        cursor.execute("""
            SELECT 
                SUM(stage0_indexed) as indexed,
                SUM(stage1_meta) as metadata,
                SUM(stage2_episode) as episode,
                SUM(stage3_rename) as filename,
                SUM(stage5_epub) as epub
            FROM processing_state
        """)
        stage_stats = cursor.fetchone()
        
        # 배치 로그 통계
        cursor.execute("""
            SELECT 
                COUNT(*) as total_batches,
                SUM(success) as total_success,
                SUM(failed) as total_failed
            FROM batch_logs
        """)
        batch_stats = cursor.fetchone()
        
        return {
            "files": {
                "total": file_stats[0],
                "duplicates": file_stats[1],
                "total_size_mb": file_stats[2] / (1024 * 1024) if file_stats[2] else 0
            },
            "stages": {
                "indexed": stage_stats[0],
                "metadata": stage_stats[1],
                "episode": stage_stats[2],
                "filename": stage_stats[3],
                "epub": stage_stats[4]
            },
            "batches": {
                "total": batch_stats[0],
                "success": batch_stats[1],
                "failed": batch_stats[2]
            }
        }
    
    def cleanup_duplicates(self) -> int:
        """중복 파일 정리 (DB에서만 제거, 실제 파일은 유지)
        
        Returns:
            정리된 중복 파일 수
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # 중복 파일 조회
        cursor.execute("""
            SELECT id FROM files WHERE is_duplicate = 1
        """)
        duplicate_ids = [row[0] for row in cursor.fetchall()]
        
        if not duplicate_ids:
            logger.info("No duplicates to clean up")
            return 0
        
        # processing_state에서 제거
        cursor.execute(f"""
            DELETE FROM processing_state 
            WHERE file_id IN ({','.join('?' * len(duplicate_ids))})
        """, duplicate_ids)
        
        # files에서 제거
        cursor.execute(f"""
            DELETE FROM files 
            WHERE id IN ({','.join('?' * len(duplicate_ids))})
        """, duplicate_ids)
        
        conn.commit()
        
        logger.info(f"✅ Cleaned up {len(duplicate_ids)} duplicate files from DB")
        return len(duplicate_ids)
