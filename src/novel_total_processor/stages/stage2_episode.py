"""Stage 2: 화수 검증

파일 샘플링 (앞뒤 20KB), AI 기반 화수 패턴 감지, 캐싱
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import chardet
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.db.schema import Database
from novel_total_processor.ai.gemini_client import GeminiClient
from novel_total_processor.config.loader import get_config

logger = get_logger(__name__)


class FileSampler:
    """파일 샘플러 (앞뒤 20KB 추출)"""
    
    def __init__(self, sample_size: int = 20480):
        """
        Args:
            sample_size: 샘플 크기 (바이트, 기본 20KB)
        """
        self.sample_size = sample_size
        logger.info(f"FileSampler initialized: sample_size={sample_size} bytes")
    
    def sample_file(self, file_path: str, encoding: Optional[str] = None) -> Tuple[str, str]:
        """파일 앞뒤 샘플 추출
        
        Args:
            file_path: 파일 경로
            encoding: 인코딩 (None이면 자동 감지)
        
        Returns:
            (앞 샘플, 뒤 샘플) 텍스트
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # 인코딩 감지
        if not encoding:
            encoding = self._detect_encoding(path)
        
        # 파일 크기 확인
        file_size = path.stat().st_size
        
        # 앞 샘플
        with open(path, "rb") as f:
            head_bytes = f.read(self.sample_size)
        
        # 뒤 샘플
        with open(path, "rb") as f:
            if file_size > self.sample_size:
                f.seek(-self.sample_size, 2)  # 끝에서 20KB 앞으로
            tail_bytes = f.read(self.sample_size)
        
        # 디코딩
        try:
            head_text = head_bytes.decode(encoding, errors="ignore")
            tail_text = tail_bytes.decode(encoding, errors="ignore")
        except Exception as e:
            logger.warning(f"Decoding failed with {encoding}: {e}, trying utf-8")
            head_text = head_bytes.decode("utf-8", errors="ignore")
            tail_text = tail_bytes.decode("utf-8", errors="ignore")
        
        return head_text, tail_text
    
    def _detect_encoding(self, file_path: Path) -> str:
        """인코딩 감지
        
        Args:
            file_path: 파일 경로
        
        Returns:
            인코딩 이름
        """
        with open(file_path, "rb") as f:
            sample = f.read(10000)
        
        result = chardet.detect(sample)
        encoding = result.get("encoding", "utf-8")
        confidence = result.get("confidence", 0)
        
        if confidence < 0.7:
            logger.warning(f"Low confidence encoding: {encoding} ({confidence:.2f})")
            encoding = "utf-8"  # Fallback
        
        return encoding


class EpisodePatternDetector:
    """화수 패턴 감지기 (AI 기반)"""
    
    def __init__(self, db: Database):
        """
        Args:
            db: Database 인스턴스
        """
        self.db = db
        self.config = get_config()
        self.gemini = GeminiClient()
        self.sampler = FileSampler()
        
        # 캐시 디렉토리
        self.cache_dir = Path("data/cache/episode_pattern")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("EpisodePatternDetector initialized")
    
    def get_pending_files(self, limit: Optional[int] = None) -> list:
        """Stage 2 대기 중인 파일 조회 (Stage 4 완료 파일)
        
        Args:
            limit: 최대 파일 수
        
        Returns:
            파일 정보 리스트
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Stage 4 완료, Stage 2 미완료 파일
        query = """
            SELECT f.id, f.file_path, f.file_hash, f.encoding
            FROM files f
            JOIN processing_state ps ON f.id = ps.file_id
            WHERE (ps.stage4_split = 1 OR f.file_ext = '.epub') 
            AND ps.stage2_episode = 0
            AND f.is_duplicate = 0 AND f.file_ext IN ('.txt', '.epub')
            ORDER BY f.id ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        files = [
            {"id": row[0], "file_path": row[1], "file_hash": row[2], "encoding": row[3]}
            for row in rows
        ]
        
        logger.info(f"Found {len(files)} files pending for Stage 2")
        return files
    
    def _get_cache_path(self, file_hash: str) -> Path:
        """캐시 파일 경로
        
        Args:
            file_hash: 파일 해시
        
        Returns:
            캐시 경로
        """
        return self.cache_dir / f"{file_hash}.json"
    
    def _load_from_cache(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """캐시에서 로드
        
        Args:
            file_hash: 파일 해시
        
        Returns:
            캐시된 패턴 또는 None
        """
        cache_path = self._get_cache_path(file_hash)
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.debug(f"Cache hit: {file_hash[:8]}...")
                return data
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")
        return None
    
    def _save_to_cache(self, file_hash: str, data: Dict[str, Any]) -> None:
        """캐시에 저장
        
        Args:
            file_hash: 파일 해시
            data: 패턴 데이터
        """
        cache_path = self._get_cache_path(file_hash)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Cache saved: {file_hash[:8]}...")
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")
    
    def detect_pattern(self, file_id: int, file_path: str, file_hash: str, encoding: Optional[str]) -> Dict[str, Any]:
        """화수 패턴 감지 (Stage 4 결과 활용)
        
        Args:
            file_id: 파일 ID
            file_path: 파일 경로
            file_hash: 파일 해시
            encoding: 인코딩
        
        Returns:
            {"pattern_regex": str, "detected_start": int, "detected_end": int, "confidence": float}
        """
        # Stage 4 캐시 확인
        stage4_cache = Path("data/cache/chapter_split") / f"{file_hash}.json"
        
        if not stage4_cache.exists():
            logger.warning(f"Stage 4 cache not found: {file_hash[:8]}... - Skipping")
            return {
                "pattern_regex": "",
                "detected_start": 1,
                "detected_end": 1,
                "confidence": 0.0
            }
        
        # Stage 4 결과 로드
        try:
            with open(stage4_cache, "r", encoding="utf-8") as f:
                stage4_data = json.load(f)
            
            summary = stage4_data.get("summary", {})
            patterns = stage4_data.get("patterns", {})
            
            # 본편 화수 범위 추출
            main_info = summary.get("본편", {})
            start = main_info.get("start", 1)
            end = main_info.get("end", 1)
            
            # 패턴 정규식
            pattern_regex = patterns.get("chapter_pattern", "")
            
            logger.info(f"   ✅ Stage 4 결과 활용: 본편 {start}~{end}화")
            
            return {
                "pattern_regex": pattern_regex,
                "detected_start": start,
                "detected_end": end,
                "confidence": 1.0  # Stage 4 결과는 신뢰도 100%
            }
        
        except Exception as e:
            logger.error(f"Failed to load Stage 4 cache: {e}")
            return {
                "pattern_regex": "",
                "detected_start": 1,
                "detected_end": 1,
                "confidence": 0.0
            }
    
    def _build_pattern_prompt(self, head_text: str, tail_text: str) -> str:
        """화수 패턴 감지 프롬프트 생성
        
        Args:
            head_text: 파일 앞부분
            tail_text: 파일 뒷부분
        
        Returns:
            프롬프트 문자열
        """
        return f"""다음은 소설 텍스트 파일의 앞부분과 뒷부분 샘플입니다.
이 파일에서 사용된 화수 표기 패턴을 분석하고, 실제 시작화와 끝화를 추출하세요.

=== 파일 앞부분 (20KB) ===
{head_text[:5000]}

=== 파일 뒷부분 (20KB) ===
{tail_text[-5000:]}

다음 형식의 JSON으로 응답하세요:
{{
  "pattern_regex": "정규식 패턴 (예: '제(\\d+)화', '\\d+화', 'Chapter \\d+' 등)",
  "detected_start": 시작화 번호 (정수),
  "detected_end": 끝화 번호 (정수),
  "confidence": 신뢰도 (0.0~1.0)
}}

규칙:
1. 가장 일관되게 나타나는 패턴을 선택
2. 프롤로그/에필로그는 무시하고 본편 화수만 추출
3. 화수가 없으면 detected_start=1, detected_end=1, confidence=0.0
4. JSON만 출력 (설명 없이)
"""
    
    def _parse_pattern_response(self, response_text: str) -> Dict[str, Any]:
        """응답 파싱
        
        Args:
            response_text: API 응답
        
        Returns:
            패턴 데이터
        """
        try:
            # JSON 추출
            json_text = response_text.strip()
            if json_text.startswith("```"):
                json_text = json_text.split("```")[1]
                if json_text.startswith("json"):
                    json_text = json_text[4:]
            
            data = json.loads(json_text.strip())
            
            return {
                "pattern_regex": data.get("pattern_regex", ""),
                "detected_start": data.get("detected_start", 1),
                "detected_end": data.get("detected_end", 1),
                "confidence": data.get("confidence", 0.0)
            }
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            logger.debug(f"Response: {response_text}")
            # Fallback
            return {
                "pattern_regex": "",
                "detected_start": 1,
                "detected_end": 1,
                "confidence": 0.0
            }
    
    def save_to_db(self, file_id: int, pattern_data: Dict[str, Any]) -> None:
        """DB에 저장
        
        Args:
            file_id: 파일 ID
            pattern_data: 패턴 데이터
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # episode_patterns 테이블
        cursor.execute("""
            INSERT OR REPLACE INTO episode_patterns 
            (file_id, pattern_regex, detected_start, detected_end, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            file_id,
            pattern_data["pattern_regex"],
            pattern_data["detected_start"],
            pattern_data["detected_end"],
            pattern_data["confidence"]
        ))
        
        # processing_state 업데이트
        cursor.execute("""
            UPDATE processing_state
            SET stage2_episode = 1, last_stage = 'stage2'
            WHERE file_id = ?
        """, (file_id,))
        
        conn.commit()
    
    def run(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Stage 2 실행
        
        Args:
            limit: 처리할 최대 파일 수
        
        Returns:
            {"total": int, "success": int, "failed": int}
        """
        logger.info("=" * 50)
        logger.info("Stage 2: Episode Pattern Detection")
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
            file_path_obj = Path(file['file_path'])
            logger.info(f"[{i+1}/{len(files)}] {file_path_obj.name}")
            
            if not file_path_obj.exists():
                logger.warning(f"   ⚠️  파일이 디스크에 없습니다. 스킵합니다: {file_path_obj}")
                failed_count += 1
                continue
                
            try:
                # EPUB인 경우: 분석된 챕터 수와 메타데이터의 기대 화수 비교 검증 (M-26)
                if file_path_obj.suffix.lower() == '.epub':
                    logger.info("   -> EPUB 원본: 화수 정합성 검증 시작")
                    cursor = self.db.connect().cursor()
                    cursor.execute("""
                        SELECT n.episode_range, n.chapter_count 
                        FROM novels n 
                        JOIN files f ON n.id = f.novel_id 
                        WHERE f.id = ?
                    """, (file["id"],))
                    res = cursor.fetchone()
                    
                    actual_count = res[1] if res and res[1] else 0
                    expected_range = res[0] if res and res[0] else "Unknown"
                    
                    # 챕터 수 검증 로직 (간단하게 숫자가 포함되어 있는지 확인)
                    expected_count = 0
                    if expected_range != "Unknown":
                        nums = re.findall(r'\d+', expected_range)
                        if len(nums) >= 2:
                            expected_count = int(nums[1]) - int(nums[0]) + 1
                        elif len(nums) == 1:
                            expected_count = int(nums[0])
                    
                    confidence = 1.0
                    if expected_count > 0:
                        diff = abs(actual_count - expected_count)
                        if diff > 5: # 5화 이상 차이 나면 의심
                            logger.warning(f"   ⚠️ 화수 불일치 의심: 실제 {actual_count}ch vs 기대 {expected_count}화 ({expected_range})")
                            confidence = 0.5
                        else:
                            logger.info(f"   ✅ 화수 검증 완료: 실제 {actual_count}ch vs 기대 {expected_count}화")
                    
                    pattern_data = {
                        "pattern_regex": "EPUB_VERIFIED",
                        "detected_start": 1,
                        "detected_end": actual_count,
                        "confidence": confidence,
                        "pattern_json": json.dumps({"type": "epub", "range": expected_range, "actual": actual_count})
                    }
                else:
                    pattern_data = self.detect_pattern(
                        file["id"],
                        file["file_path"],
                        file["file_hash"],
                        file["encoding"]
                    )
                
                self.save_to_db(file["id"], pattern_data)
                
                if file_path_obj.suffix.lower() != '.epub': # Changed file_path to file_path_obj
                    logger.debug(f"  Pattern: {pattern_data['pattern_regex']}")
                    logger.debug(f"  Range: {pattern_data['detected_start']}~{pattern_data['detected_end']}")
                    logger.debug(f"  Confidence: {pattern_data['confidence']:.2f}")
                
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to process {file_path_obj.name}: {e}")
                failed_count += 1
        
        logger.info("=" * 50)
        logger.info(f"✅ Stage 2 Complete: {success_count} success, {failed_count} failed")
        logger.info("=" * 50)
        
        return {
            "total": len(files),
            "success": success_count,
            "failed": failed_count
        }
