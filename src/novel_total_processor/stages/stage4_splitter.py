"""Stage 4: 챕터 분할

AI 패턴 분석 → 정규식 → 챕터 분할 → 본편/외전 분류
NovelAIze-SSR v3.0 포팅 + 챕터 제목 분석 추가
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.db.schema import Database
from novel_total_processor.config.loader import get_config
from novel_total_processor.ai.gemini_client import GeminiClient
from novel_total_processor.stages.sampler import Sampler
from novel_total_processor.stages.pattern_manager import PatternManager
from novel_total_processor.stages.splitter import Splitter
from novel_total_processor.stages.chapter import Chapter

logger = get_logger(__name__)


class ChapterSplitRunner:
    """Stage 4: 챕터 분할 메인 실행기"""
    
    def __init__(self, db: Database):
        """
        Args:
            db: Database 인스턴스
        """
        self.db = db
        self.config = get_config()
        self.client = GeminiClient()
        self.sampler = Sampler()
        self.pattern_manager = PatternManager(self.client)
        self.splitter = Splitter()
        
        # 캐시 디렉토리
        self.cache_dir = Path("data/cache/chapter_split")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("ChapterSplitRunner initialized")
    
    def get_pending_files(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Stage 4 대기 중인 파일 조회
        
        Args:
            limit: 최대 파일 수
        
        Returns:
            파일 정보 리스트
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        query = """
            SELECT f.id, f.file_path, f.file_name, f.file_hash, f.encoding
            FROM files f
            JOIN processing_state ps ON f.id = ps.file_id
            WHERE ps.stage1_meta = 1 AND ps.stage4_split = 0
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
                "encoding": row[4]
            })
        
        logger.info(f"Found {len(files)} files pending for Stage 4")
        return files
    
    def split_chapters(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """챕터 분할 실행
        
        Args:
            file_info: 파일 정보
        
        Returns:
            분할 결과 {"chapters": List[Chapter], "summary": dict}
        """
        file_path = file_info["file_path"]
        file_hash = file_info["file_hash"]
        
        # 1. 샘플 추출
        logger.info(f"   -> 샘플 추출 중... (30개 균등 샘플)")
        samples = self.sampler.extract_samples(file_path)
        
        # 2. AI 패턴 분석
        logger.info(f"   -> AI 패턴 분석 중...")
        chapter_pattern, subtitle_pattern = self.pattern_manager.find_best_pattern(
            file_path,
            samples
        )
        
        if not chapter_pattern:
            raise ValueError("챕터 패턴을 찾을 수 없습니다")
        
        logger.info(f"   ✅ 최종 패턴: {chapter_pattern}")
        if subtitle_pattern:
            logger.info(f"   ✅ 소제목 패턴: {subtitle_pattern}")
        
        # 3. 챕터 분할
        logger.info(f"   -> 챕터 분할 중...")
        chapters = list(self.splitter.split(file_path, chapter_pattern, subtitle_pattern))
        
        logger.info(f"   ✅ 총 {len(chapters)}개 챕터 분할 완료")
        
        # 4. 챕터 제목 분석 (본편/외전/에필로그 분류)
        summary = self._analyze_chapter_types(chapters)
        
        # 5. 결과 저장
        result = {
            "chapters": [
                {
                    "cid": ch.cid,
                    "title": ch.title,
                    "subtitle": ch.subtitle,
                    "length": ch.length,
                    "chapter_type": ch.chapter_type
                }
                for ch in chapters
            ],
            "summary": summary,
            "patterns": {
                "chapter_pattern": chapter_pattern,
                "subtitle_pattern": subtitle_pattern
            }
        }
        
        # 캐시 저장
        cache_path = self.cache_dir / f"{file_hash}.json"
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"   ✅ 캐시 저장: {cache_path}")
        
        return result
    
    def _analyze_chapter_types(self, chapters: List[Chapter]) -> Dict[str, Any]:
        """챕터 제목 분석하여 본편/외전/에필로그 분류
        
        Args:
            chapters: 챕터 리스트
        
        Returns:
            {"본편": {"start": 1, "end": 340, "count": 340}, ...}
        """
        # 키워드 기반 분류
        main_keywords = ["화", "chapter", "제"]
        extra_keywords = ["외전", "번외", "특별편", "side story"]
        epilogue_keywords = ["에필로그", "epilogue", "후일담", "완결"]
        author_keywords = ["작가의 말", "작가 후기", "후기"]
        
        summary = {
            "본편": {"chapters": [], "count": 0},
            "외전": {"chapters": [], "count": 0},
            "에필로그": {"chapters": [], "count": 0},
            "작가의 말": {"chapters": [], "count": 0},
            "기타": {"chapters": [], "count": 0},
            "total": len(chapters)
        }
        
        for ch in chapters:
            title_lower = ch.title.lower()
            
            # 작가의 말
            if any(kw in title_lower for kw in author_keywords):
                ch.chapter_type = "작가의 말"
                summary["작가의 말"]["chapters"].append(ch.cid)
            
            # 에필로그
            elif any(kw in title_lower for kw in epilogue_keywords):
                ch.chapter_type = "에필로그"
                summary["에필로그"]["chapters"].append(ch.cid)
            
            # 외전
            elif any(kw in title_lower for kw in extra_keywords):
                ch.chapter_type = "외전"
                summary["외전"]["chapters"].append(ch.cid)
            
            # 본편 (기본값)
            else:
                ch.chapter_type = "본편"
                summary["본편"]["chapters"].append(ch.cid)
        
        # 각 타입별 시작/끝 화수 계산
        for type_name, info in summary.items():
            if type_name == "total":
                continue
            
            if info["chapters"]:
                info["count"] = len(info["chapters"])
                info["start"] = min(info["chapters"]) + 1  # cid는 0부터, 화수는 1부터
                info["end"] = max(info["chapters"]) + 1
            else:
                info["start"] = 0
                info["end"] = 0
        
        logger.info(f"   📊 챕터 분류:")
        logger.info(f"      본편: {summary['본편']['count']}개 ({summary['본편']['start']}~{summary['본편']['end']}화)")
        if summary['외전']['count'] > 0:
            logger.info(f"      외전: {summary['외전']['count']}개 ({summary['외전']['start']}~{summary['외전']['end']}화)")
        if summary['에필로그']['count'] > 0:
            logger.info(f"      에필로그: {summary['에필로그']['count']}개")
        if summary['작가의 말']['count'] > 0:
            logger.info(f"      작가의 말: {summary['작가의 말']['count']}개")
        
        return summary
    
    def save_to_db(self, file_id: int, result: Dict[str, Any]) -> None:
        """DB에 저장
        
        Args:
            file_id: 파일 ID
            result: 분할 결과
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        summary = result["summary"]
        
        # novels 테이블 업데이트 (챕터 수 저장)
        cursor.execute("""
            UPDATE novels
            SET chapter_count = ?, updated_at = datetime('now','localtime')
            WHERE id = (SELECT novel_id FROM files WHERE id = ?)
        """, (summary["total"], file_id))
        
        # processing_state 업데이트
        cursor.execute("""
            UPDATE processing_state
            SET stage4_split = 1, last_stage = 'stage4', updated_at = datetime('now','localtime')
            WHERE file_id = ?
        """, (file_id,))
        
        conn.commit()
    
    def run(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Stage 4 실행
        
        Args:
            limit: 처리할 최대 파일 수
        
        Returns:
            {"total": int, "success": int, "failed": int}
        """
        logger.info("=" * 50)
        logger.info("Stage 4: Chapter Splitting")
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
            logger.info(f"[{i+1}/{len(files)}] {file_info['file_name']}")
            
            try:
                result = self.split_chapters(file_info)
                self.save_to_db(file_info["file_id"], result)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to split chapters: {e}")
                failed_count += 1
        
        logger.info("=" * 50)
        logger.info(f"✅ Stage 4 Complete: {success_count} success, {failed_count} failed")
        logger.info("=" * 50)
        
        return {
            "total": len(files),
            "success": success_count,
            "failed": failed_count
        }
