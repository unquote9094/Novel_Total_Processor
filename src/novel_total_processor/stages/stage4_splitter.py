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
from novel_total_processor.stages.stage3_filename import FilenameGenerator

logger = get_logger(__name__)


class ChapterSplitRunner:
    """Stage 4: 챕터 분할 메인 실행기"""
    
    # Enhanced recovery constants
    MAX_RETRIES = 5  # Increased from 3 to support more recovery attempts
    TITLE_CANDIDATE_RETRY_THRESHOLD = 2  # Start using title candidates after this many retries
    MAX_GAPS_TO_ANALYZE = 3  # Limit gap analysis to top N gaps for efficiency
    
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
        self.filename_generator = FilenameGenerator(self.db)
        
        # 캐시 디렉토리
        self.cache_dir = Path("data/cache/chapter_split")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("ChapterSplitRunner initialized")
    
    def get_pending_files(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Stage 4 대기 중인 파일 조회 (M-45: Force/Retry 지원)"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # [M-45 보강] stage1_meta가 1인데, stage4_split이 0이거나, 
        # 혹은 화수 정합성이 실패하여 재작업이 필요한 파일을 모두 가져옴
        query = """
            SELECT f.id, f.file_path, f.file_name, f.file_hash, f.encoding
            FROM files f
            JOIN processing_state ps ON f.id = ps.file_id
            WHERE ps.stage1_meta = 1 
            AND (ps.stage4_split = 0 OR ps.stage4_split = 1) -- 테스트 및 재분석을 위해 완료된 파일도 포함
            AND f.is_duplicate = 0 AND f.file_ext IN ('.txt', '.epub')
            ORDER BY ps.stage4_split ASC, f.id ASC -- 미완료 파일을 우선순위로
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
        encoding = file_info.get("encoding", "utf-8") or "utf-8"
        
        if file_path.lower().endswith('.epub'):
            # 1. EPUB 내부 챕터 분석 (Duokan 등 표준 구조)
            logger.info(f"   -> EPUB 내부 구조 정밀 분석 중...")
            from ebooklib import epub
            book = epub.read_epub(file_path)
            chapters = []
            
            # Spine 순서대로 본문 아이템만 추출
            cid = 1
            content_items = []
            
            # Spine에 등록된 아이템 ID 목록
            spine_ids = [s[0] for s in book.spine if isinstance(s, tuple)]
            
            for item_id in spine_ids:
                item = book.get_item_with_id(item_id)
                if not item or item.get_type() != 9: # ITEM_DOCUMENT
                    continue
                
                name = item.get_name().lower()
                # 비본문 섹션 제외 (M-32)
                if any(x in name for x in ['cover', 'nav', 'toc', 'titlepage', 'metadata']):
                    continue
                
                content = item.get_content().decode('utf-8', errors='ignore')
                
                # 본문 내용이 너무 짧으면 제외 (예: 단순 이미지 페이지나 공백)
                text_only = re.sub(r'<[^>]*>', '', content).strip()
                if len(text_only) < 50 and 'img' not in content.lower():
                    continue
                
                # 제목 추출
                title = item.get_name()
                match = re.search(r'<(?:h1|h2|title)[^>]*>(.*?)</(?:h1|h2|title)>', content, re.IGNORECASE | re.DOTALL)
                if match:
                    title = re.sub(r'<[^>]*>', '', match.group(1)).strip()
                
                # 제목에 순번 부여 (M-32)
                # 만약 제목에 이미 숫자가 있다면 최대한 활용, 없다면 [cid] 추가
                if not re.search(r'\d+', title):
                    display_title = f"[{cid}] {title}"
                else:
                    display_title = title
                
                chapters.append(Chapter(
                    cid=cid,
                    title=display_title,
                    subtitle="",
                    body=content,
                    length=len(content)
                ))
                cid += 1
            
            chapter_pattern = "EPUB_STRUCTURE"
            subtitle_pattern = None
        else:
            # 1. 샘플 추출 (M-16: Dynamic Encoding 적용)
            logger.info(f"   -> 샘플 추출 중... (30개 균등 샘플, 인코딩: {encoding})")
            samples = self.sampler.extract_samples(file_path, encoding=encoding)
            
            # 2. AI 패턴 분석 (M-28: 파일명 힌트 활용)
            logger.info(f"   -> AI 패턴 분석 중...")
            chapter_pattern, subtitle_pattern = self.pattern_manager.find_best_pattern(
                file_path,
                samples,
                filename=file_info["file_name"],
                encoding=encoding
            )
            
            if not chapter_pattern:
                raise ValueError("챕터 패턴을 찾을 수 없습니다")
            
            # 3. 챕터 분할
            logger.info(f"   -> 챕터 분할 중...")
            chapters = list(self.splitter.split(file_path, chapter_pattern, subtitle_pattern, encoding=encoding))
            
            # 3-1. 정합성 검증 및 자동 재분석 (M-29/45/49: Zero Tolerance 100% Match)
            # Enhanced with multi-signal recovery: pattern → verify → gaps → title candidates → consensus
            nums = re.findall(r'\d+', file_info["file_name"])
            expected_count = int(nums[-1]) if nums else 0
            
            reconciliation_log = []
            
            # Enhanced recovery loop with multi-signal detection
            # 부족하거나(Under) 넘칠 때(Over) 모두 정밀 분석 트리거
            retry_count = 0
            title_candidates_used = False
            
            while expected_count > 0 and len(chapters) != expected_count and retry_count < self.MAX_RETRIES:
                retry_count += 1
                logger.error(f"   ❌ [Mismatch] 화수 불일치 감지 ({len(chapters)}/{expected_count}). 재시도({retry_count}/{self.MAX_RETRIES})를 시작합니다.")
                
                # 가이드 힌트 준비
                missing = self._find_missing_episodes(chapters, expected_count)
                reconciliation_log.append(f"시도 {retry_count}: {len(chapters)}화 추출 (기대 {expected_count})")
                
                # Get current match positions for gap analysis
                matches = self.splitter.find_matches_with_pos(file_path, chapter_pattern, encoding=encoding)
                
                # 동적 갭 분석 및 패턴 보강
                refined_pattern = self.pattern_manager.refine_pattern_with_goal_v3(
                    file_path,
                    chapter_pattern,
                    expected_count,
                    encoding=encoding
                )
                
                if refined_pattern != chapter_pattern:
                    chapter_pattern = refined_pattern
                    logger.info("   -> [Self-Healing] 수정된 패턴으로 재분할 중...")
                    chapters = list(self.splitter.split(file_path, chapter_pattern, subtitle_pattern, encoding=encoding))
                    
                    # If still missing after pattern refinement, try title candidates (on later retries)
                    if retry_count >= self.TITLE_CANDIDATE_RETRY_THRESHOLD and len(chapters) < expected_count:
                        logger.info("   -> [Fallback] 타이틀 후보 탐지 시도 중...")
                        missing_count = expected_count - len(chapters)
                        
                        # Find gaps using dynamic detection
                        gaps = self.pattern_manager.find_dynamic_gaps(file_path, matches, expected_count)
                        
                        # Extract title candidates from top gaps
                        all_candidates = []
                        for gap in gaps[:self.MAX_GAPS_TO_ANALYZE]:
                            sample = self.sampler.extract_samples_from(
                                file_path, gap['start'], length=30000, encoding=encoding
                            )
                            if sample:
                                candidates = self.pattern_manager.extract_title_candidates(
                                    sample, chapter_pattern
                                )
                                all_candidates.extend(candidates)
                        
                        if all_candidates:
                            # Try splitting with explicit title candidates
                            logger.info(f"   -> [Consensus] {len(all_candidates)} 타이틀 후보로 재분할 시도...")
                            chapters = list(self.splitter.split(
                                file_path, chapter_pattern, subtitle_pattern, 
                                encoding=encoding, title_candidates=all_candidates
                            ))
                            title_candidates_used = True
                            reconciliation_log.append(f"타이틀 후보 {len(all_candidates)}개 사용")
                else:
                    logger.warning("   -> 패턴 보강에 실패했습니다. 다음 시도로 넘어갑니다.")
            
            # 최종 정합성 로그 기록
            if expected_count > 0 and len(chapters) != expected_count:
                reason = f"최종 화수 불일치: 보유 {len(chapters)} / 웹(또는 힌트) {expected_count}"
                logger.error(f"   -> [Strict Match Fail] {reason}")
                reconciliation_log.append(reason)
                # 누락된 회차 정보 추가
                missing = self._find_missing_episodes(chapters, expected_count)
                if missing:
                    reconciliation_log.append(f"누락 의심: {', '.join(map(str, missing[:10]))} 등")
                
                # Log recovery methods used
                if title_candidates_used:
                    reconciliation_log.append("복구 방법: 패턴 + 타이틀 후보 (consensus)")
            elif expected_count > 0:
                logger.info(f"   ✅ 화수 100% 일치 확인: {len(chapters)}화 (Perfect Match)")
                reconciliation_log.append(f"정합성 100% 일치 ({len(chapters)}화)")
                if title_candidates_used:
                    reconciliation_log.append("복구 방법: 타이틀 후보 (consensus) 사용됨")
            
            file_info["reconciliation_log"] = "\n".join(reconciliation_log)
            self._verify_chapter_count(file_info["file_name"], len(chapters), chapters)
        
        logger.info(f"   ✅ 총 {len(chapters)}개 챕터 확인 완료")
        
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
            },
            "reconciliation_log": file_info.get("reconciliation_log", "")
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
        main_keywords = ["화", "chapter", "제", "ep"]
        extra_keywords = ["외전", "번외", "특별편", "side story"]
        # "완결"은 본편 마지막화에 자주 붙으므로 에필로그 키워드에서 제외 (단독 사용 시 에필로그 취급 고려)
        epilogue_keywords = ["에필로그", "epilogue", "후일담"]
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
    
    def _verify_chapter_count(self, filename: str, actual_count: int, chapters: List[Chapter]) -> None:
        """파일명의 화수 힌트와 실제 분할된 챕터 수 비교 검증 (M-28/45/48)"""
        nums = re.findall(r'\d+', filename)
        if not nums:
            return
        
        expected_count = int(nums[-1])
        if expected_count > 0:
            diff = actual_count - expected_count
            if diff < 0:
                logger.error("=" * 60)
                logger.error(f"❌ [정합성 실패] 화수가 부족합니다! ({actual_count}/{expected_count})")
                missing = self._find_missing_episodes(chapters, expected_count)
                if missing:
                    logger.error(f"   - 누락된 회차 예상: {missing[:20]}{'...' if len(missing)>20 else ''}")
                logger.error("=" * 60)
            elif diff > 0:
                logger.warning("=" * 60)
                logger.warning(f"⚠️  [정합성 경고] 화수가 기대치보다 많습니다. ({actual_count}/{expected_count})")
                logger.warning("   - 중복 매칭이나 외전이 포함되었을 수 있습니다.")
                logger.warning("=" * 60)
            else:
                logger.info(f"   ✅ 화수 100% 일치 확인: {actual_count}화 (Perfect Match)")

    def _find_missing_episodes(self, chapters: List[Chapter], expected_count: int) -> List[int]:
        """추출된 챕터들 사이에서 빠진 번호 탐지 (M-48)"""
        found_nums = set()
        for ch in chapters:
            # 제목에서 첫 번째 숫자 추출
            match = re.search(r'(\d+)', ch.title)
            if match:
                found_nums.add(int(match.group(1)))
        
        missing = []
        for i in range(1, expected_count + 1):
            if i not in found_nums:
                missing.append(i)
        return missing

    def save_to_db(self, file_id: int, result: Dict[str, Any]) -> None:
        """DB에 저장
        
        Args:
            file_id: 파일 ID
            result: 분할 결과
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        summary = result["summary"]
        
        # novels 테이블 업데이트 (챕터 수 및 정합성 로그 저장)
        reconcile_log = result.get("reconciliation_log", "")
        cursor.execute("""
            UPDATE novels
            SET chapter_count = ?, reconciliation_log = ?
            WHERE id = (SELECT novel_id FROM files WHERE id = ?)
        """, (summary["total"], reconcile_log, file_id))
        
        # processing_state 업데이트 (정합성 로그 포함)
        cursor.execute("""
            UPDATE processing_state
            SET stage4_split = 1, last_stage = 'stage4', reconciliation_log = ?
            WHERE file_id = ?
        """, (reconcile_log, file_id))
        
        conn.commit()
        
        # [M-49] 분석 완료 후 실물 데이터 기반으로 파일명 최종 동기화 (Sync Original TXT)
        try:
            logger.info(f"   -> [Sync] 실물 기반 파일명 최종 동기화 시도 중... (File ID: {file_id})")
            self.filename_generator.process_single_file(file_id)
        except Exception as e:
            logger.error(f"   ❌ [Sync Fail] 파일명 동기화 중 오류 발생: {e}")
    
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
            file_path_obj = Path(file_info['file_path'])
            logger.info(f"[{i+1}/{len(files)}] {file_path_obj.name}")
            
            if not file_path_obj.exists():
                logger.warning(f"   ⚠️  파일이 디스크에 없습니다. 스킵합니다: {file_path_obj}")
                failed_count += 1 # Treat as failed since it couldn't be processed
                continue
                
            try:
                result = self.split_chapters(file_info)
                self.save_to_db(file_info["file_id"], result)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to split chapters for {file_path_obj.name}: {e}")
                # [Hotfix v2] 실패 시 기존 오염된 캐시가 있다면 삭제 (Stage 5 오염 방지)
                cache_path = self.cache_dir / f"{file_info['file_hash']}.json"
                if cache_path.exists():
                    try:
                        cache_path.unlink()
                        logger.info(f"   🗑️  실패한 파일의 기존 캐시를 삭제했습니다.")
                    except: pass
                
                failed_count += 1
        
        logger.info("=" * 50)
        logger.info(f"✅ Stage 4 Complete: {success_count} success, {failed_count} failed")
        logger.info("=" * 50)
        
        return {
            "total": len(files),
            "success": success_count,
            "failed": failed_count
        }
