"""Stage 4: 챕터 분할

AI 패턴 분석 → 정규식 → 챕터 분할 → 본편/외전 분류
NovelAIze-SSR v3.0 포팅 + 챕터 제목 분석 추가

NOTE: Pattern recognition and generation uses GeminiClient only.
Perplexity is NOT used for pattern analysis - it's reserved for
Stage 1 metadata search/grounding only.
"""

import json
import re
import os
import tempfile
import traceback
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
from novel_total_processor.stages.structural_analyzer import StructuralAnalyzer
from novel_total_processor.stages.ai_scorer import AIScorer
from novel_total_processor.stages.global_optimizer import GlobalOptimizer
from novel_total_processor.stages.topic_change_detector import TopicChangeDetector

logger = get_logger(__name__)


class ChapterSplitRunner:
    """Stage 4: 챕터 분할 메인 실행기"""
    
    # Enhanced recovery constants
    MAX_RETRIES = 5  # Increased from 3 to support more recovery attempts
    TITLE_CANDIDATE_RETRY_THRESHOLD = 2  # Start using title candidates after this many retries
    MAX_GAPS_TO_ANALYZE = 3  # Limit gap analysis to top N gaps for efficiency
    ESTIMATED_AVG_LINE_BYTES = 1000  # Estimated average bytes per line for position calculations
    
    # Quality validation constants
    MIN_VALID_CHAPTER_LENGTH = 100  # Minimum characters for a valid chapter
    MAX_EMPTY_CHAPTER_RATIO = 0.1  # Maximum ratio of empty chapters (10%)
    MIN_AVG_CHAPTER_LENGTH = 500  # Minimum average chapter length in characters
    MIN_DISTANCE_FROM_ANCHOR = 10  # Minimum line distance from anchors when filtering candidates
    
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
        
        # Advanced escalation components
        self.structural_analyzer = StructuralAnalyzer()
        self.ai_scorer = AIScorer(self.client)
        self.global_optimizer = GlobalOptimizer()
        self.topic_detector = TopicChangeDetector(self.client)
        
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
            
            # EPUB fallback: Check chapter count against expected
            nums = re.findall(r'\d+', file_info["file_name"])
            expected_count = int(nums[-1]) if nums else 0
            
            if expected_count > 0 and len(chapters) != expected_count:
                logger.warning(f"   ⚠️  EPUB chapter count mismatch ({len(chapters)}/{expected_count})")
                logger.info(f"   🔄 Attempting text-based fallback for EPUB...")
                
                # Try to extract text from EPUB and use text-based splitting
                try:
                    # Extract full text from EPUB
                    full_text = []
                    for item_id in spine_ids:
                        item = book.get_item_with_id(item_id)
                        if item and item.get_type() == 9:
                            content = item.get_content().decode('utf-8', errors='ignore')
                            text_only = re.sub(r'<[^>]*>', '', content).strip()
                            if text_only:
                                full_text.append(text_only)
                    
                    # Write to temp file for text-based processing
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
                        tmp_path = tmp.name
                        tmp.write('\n\n'.join(full_text))
                    
                    # Try text-based advanced escalation
                    logger.info(f"   -> Extracted EPUB text to temp file, running text-based splitting...")
                    reconciliation_log = []
                    text_chapters = self._advanced_escalation_pipeline(
                        tmp_path,
                        expected_count,
                        'utf-8',
                        reconciliation_log
                    )
                    
                    # Clean up temp file
                    os.unlink(tmp_path)
                    
                    if text_chapters and len(text_chapters) == expected_count:
                        logger.info(f"   ✅ EPUB text-based fallback SUCCESS: {len(text_chapters)} chapters")
                        chapters = text_chapters
                        chapter_pattern = "EPUB_TEXT_FALLBACK"
                    else:
                        logger.warning(f"   ⚠️  EPUB text-based fallback partial/failed")
                        logger.info(f"   -> Keeping original EPUB structure ({len(chapters)} chapters)")
                        
                except Exception as e:
                    logger.error(f"   ❌ EPUB text-based fallback error: {e}")
                    logger.info(f"   -> Keeping original EPUB structure ({len(chapters)} chapters)")
            
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
            # Under/Over detection: triggers detailed analysis for mismatch cases
            retry_count = 0
            title_candidates_used = False
            
            # Fix #4: Track chapter count history for stagnation detection
            chapter_count_history = []
            STAGNATION_THRESHOLD = 3  # Number of attempts with no meaningful change to trigger escalation
            
            # Requirement #2: Track consecutive pattern refinement rejections
            consecutive_rejection_count = 0
            REJECTION_THRESHOLD = 2  # Trigger escalation after 2 consecutive rejections
            
            while expected_count > 0 and len(chapters) != expected_count and retry_count < self.MAX_RETRIES:
                retry_count += 1
                logger.error(f"   ❌ [Mismatch] 화수 불일치 감지 ({len(chapters)}/{expected_count}). 재시도({retry_count}/{self.MAX_RETRIES})를 시작합니다.")
                
                # Fix #4: Check for stagnation (no meaningful chapter count change for 3 consecutive attempts)
                chapter_count_history.append(len(chapters))
                if self._is_stagnant(chapter_count_history, STAGNATION_THRESHOLD):
                    logger.warning("=" * 60)
                    logger.warning(f"   🚨 Escalation reason: Stagnation detected")
                    logger.warning(f"      → No meaningful change (+/-2 or less) for {STAGNATION_THRESHOLD} consecutive attempts")
                    logger.warning(f"      → Chapter counts: {chapter_count_history[-STAGNATION_THRESHOLD:]}")
                    logger.warning(f"   🚀 Triggering early escalation to advanced pipeline...")
                    logger.warning("=" * 60)
                    reconciliation_log.append(f"정체 감지: {STAGNATION_THRESHOLD}회 연속 미미한 변화 ({chapter_count_history[-STAGNATION_THRESHOLD:]})")
                    break  # Exit retry loop and proceed to advanced escalation
                
                # 가이드 힌트 준비
                missing = self._find_missing_episodes(chapters, expected_count)
                reconciliation_log.append(f"시도 {retry_count}: {len(chapters)}화 추출 (기대 {expected_count})")
                
                # Get current match positions for gap analysis
                matches = self.splitter.find_matches_with_pos(file_path, chapter_pattern, encoding=encoding)
                
                # 동적 갭 분석 및 패턴 보강 (with rejection tracking)
                refined_pattern, rejection_count = self.pattern_manager.refine_pattern_with_goal_v3(
                    file_path,
                    chapter_pattern,
                    expected_count,
                    encoding=encoding,
                    max_gaps=self.MAX_GAPS_TO_ANALYZE
                )
                
                # Requirement #2: Track consecutive rejections
                if rejection_count > 0:
                    consecutive_rejection_count += rejection_count
                    if consecutive_rejection_count >= REJECTION_THRESHOLD:
                        logger.warning("=" * 60)
                        logger.warning(f"   🚨 Escalation reason: Consecutive pattern refinement rejections")
                        logger.warning(f"      → {consecutive_rejection_count} consecutive rejections detected")
                        logger.warning(f"   🚀 Triggering immediate escalation to advanced pipeline...")
                        logger.warning("=" * 60)
                        reconciliation_log.append(f"연속 거절: {consecutive_rejection_count}회 패턴 보강 거절")
                        break  # Exit retry loop and proceed to advanced escalation
                else:
                    consecutive_rejection_count = 0  # Reset on success
                
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
                        
                        # Extract title candidates from top gaps (limited by MAX_GAPS_TO_ANALYZE)
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
            
            # [Stage 4 Advanced Escalation] - Activate if pattern-based methods failed
            if expected_count > 0 and len(chapters) != expected_count:
                logger.warning("=" * 60)
                logger.warning(f"   🚨 Pattern-based methods exhausted ({len(chapters)}/{expected_count})")
                logger.warning("=" * 60)
                
                # Step 1: Try Level 3 AI direct search first (faster and more accurate than Advanced Pipeline)
                logger.info(f"   🚀 Step 1: Attempting Level 3 AI direct title search...")
                
                try:
                    # Get current matches for context
                    existing_matches = self.splitter.find_matches_with_pos(file_path, chapter_pattern, encoding=encoding)
                    
                    # Call Level 3 direct search
                    found_titles = self.pattern_manager.direct_ai_title_search(
                        file_path, chapter_pattern, expected_count, existing_matches, encoding
                    )
                    
                    if found_titles and len(found_titles) >= expected_count * 0.5:
                        logger.info(f"   ✨ [Level 3] Found {len(found_titles)} titles via AI direct search")
                        
                        # Build pattern from found titles (reverse extraction)
                        reverse_pattern = self.pattern_manager._build_pattern_from_examples(found_titles)
                        
                        if reverse_pattern:
                            # Combine with existing pattern
                            combined_pattern = f"{chapter_pattern}|{reverse_pattern}"
                            logger.info(f"   🔧 Testing combined pattern with reverse-extracted regex...")
                            
                            # Try splitting with combined pattern
                            level3_chapters = list(self.splitter.split(
                                file_path, combined_pattern, subtitle_pattern, encoding=encoding
                            ))
                            
                            # Check if Level 3 succeeded
                            if len(level3_chapters) == expected_count:
                                logger.info(f"   ✅ [Level 3 SUCCESS] Exact match: {len(level3_chapters)} chapters")
                                chapters = level3_chapters
                                chapter_pattern = combined_pattern
                                reconciliation_log.append(f"Level 3 AI 직접 탐색 성공: {len(chapters)}화")
                            elif abs(len(level3_chapters) - expected_count) < abs(len(chapters) - expected_count):
                                logger.info(f"   ✨ [Level 3 Improved] Better result: {len(chapters)} -> {len(level3_chapters)}")
                                chapters = level3_chapters
                                chapter_pattern = combined_pattern
                                reconciliation_log.append(f"Level 3 개선: {len(chapters)}화")
                            else:
                                logger.info(f"   ℹ️  [Level 3] No improvement ({len(level3_chapters)} vs {len(chapters)})")
                        else:
                            logger.warning(f"   ⚠️  [Level 3] Failed to build reverse pattern")
                    else:
                        logger.info(f"   ℹ️  [Level 3] Insufficient titles found ({len(found_titles) if found_titles else 0})")
                        
                except Exception as e:
                    logger.error(f"   ❌ [Level 3] Error during direct search: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                
                # Step 2: If Level 3 didn't achieve exact match, try Advanced Pipeline as fallback
                if len(chapters) != expected_count:
                    logger.warning(f"   🚀 Step 2: Activating Advanced Escalation Pipeline (fallback)...")
                    logger.warning("=" * 60)
                    
                    # Convert pattern-based matches to anchor boundaries
                    anchor_boundaries = None
                    if existing_matches:
                        logger.info(f"   🔧 Converting {len(existing_matches)} pattern matches to anchor boundaries...")
                        anchor_boundaries = []
                        
                        for match in existing_matches:
                            # Convert pos to line_num
                            line_num = self._pos_to_line_num(file_path, match['pos'], encoding)
                            anchor_boundaries.append({
                                'line_num': line_num,
                                'text': match['title'],
                                'confidence': 1.0,  # Pattern matches have high confidence
                                'byte_pos': match['pos']
                            })
                        
                        logger.info(f"   ✅ Created {len(anchor_boundaries)} anchor boundaries from pattern matches")
                    
                    # Try advanced escalation with anchors
                    advanced_chapters = self._advanced_escalation_pipeline(
                        file_path,
                        expected_count,
                        encoding,
                        reconciliation_log,
                        anchor_boundaries=anchor_boundaries
                    )
                    
                    if advanced_chapters and len(advanced_chapters) == expected_count:
                        logger.info(f"   ✅ Advanced escalation SUCCESS: {len(advanced_chapters)} chapters")
                        chapters = advanced_chapters
                        reconciliation_log.append(f"Advanced escalation 성공: {len(chapters)}화 추출")
                    elif advanced_chapters:
                        logger.warning(f"   ⚠️  Advanced escalation partial: {len(advanced_chapters)}/{expected_count}")
                        # Use if closer to target than current
                        if abs(len(advanced_chapters) - expected_count) < abs(len(chapters) - expected_count):
                            logger.info("   -> 부분 성공이지만 기존보다 나음. 적용합니다.")
                            chapters = advanced_chapters
                            reconciliation_log.append(f"Advanced escalation 부분 성공: {len(chapters)}화")
                    else:
                        logger.error("   ❌ Advanced escalation failed")
                        reconciliation_log.append("Advanced escalation 실패")
            
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
                    "body": ch.body,  # Save full chapter body for Stage 5
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
    
    def _advanced_escalation_pipeline(
        self,
        file_path: str,
        expected_count: int,
        encoding: str,
        reconciliation_log: List[str],
        anchor_boundaries: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[List[Chapter]]:
        """Advanced Stage 4 escalation pipeline with AI-scored candidates and global optimization
        
        Pipeline stages:
        1. Structural analysis: Generate transition point candidates
        2. AI scoring: Score each candidate for likelihood
        3. Topic change detection: Add semantic boundaries as fallback
        4. Global optimization: Select exactly expected_count boundaries
        5. Split using selected boundaries
        
        Args:
            file_path: Path to the novel file
            expected_count: Expected number of chapters
            encoding: File encoding
            reconciliation_log: Log list to append messages
            
        Returns:
            List of Chapter objects or None if failed
        """
        try:
            # Fix #5: Enhanced logging for pipeline execution
            logger.info("=" * 70)
            logger.info("   🚀 ADVANCED ESCALATION PIPELINE ACTIVATED")
            logger.info("=" * 70)
            
            # Log anchor information if present
            if anchor_boundaries:
                logger.info(f"   🔒 Using {len(anchor_boundaries)} anchor boundaries from pattern matching")
                reconciliation_log.append(f"Anchors: {len(anchor_boundaries)} pattern matching results fixed")
            
            # Stage 1: Generate structural candidates
            logger.info("   📊 [Pipeline Stage 1/5] Structural transition point analysis...")
            logger.info(f"      → Analyzing file structure for chapter boundaries")
            candidates = self.structural_analyzer.generate_candidates(
                file_path,
                encoding=encoding,
                max_candidates=expected_count * 5  # Generate 5x for good coverage
            )
            
            if not candidates:
                logger.error("   ❌ [Stage 1 Failed] No structural candidates found")
                return None
            
            logger.info(f"   ✅ [Stage 1 Complete] Generated {len(candidates)} structural candidates")
            reconciliation_log.append(f"구조 분석: {len(candidates)} 후보 생성")
            
            # Filter out candidates near anchors to reduce AI scoring load
            if anchor_boundaries and len(candidates) > 200:
                logger.info(f"   🔧 Filtering candidates near anchors to reduce AI scoring load...")
                filtered_candidates = []
                
                for cand in candidates:
                    is_near_anchor = False
                    for anchor in anchor_boundaries:
                        if abs(cand['line_num'] - anchor['line_num']) < self.MIN_DISTANCE_FROM_ANCHOR:
                            is_near_anchor = True
                            break
                    if not is_near_anchor:
                        filtered_candidates.append(cand)
                
                logger.info(f"   📊 Filtered from {len(candidates)} to {len(filtered_candidates)} candidates")
                candidates = filtered_candidates
            
            # Stage 2: AI scoring (optional, can be expensive for large candidate sets)
            # Only score if we have a reasonable number of candidates
            if len(candidates) <= 200:  # Limit to prevent excessive API calls
                logger.info("   🤖 [Pipeline Stage 2/5] AI likelihood scoring...")
                logger.info(f"      → Scoring {len(candidates)} candidates with AI (batch_size=10)")
                candidates = self.ai_scorer.score_candidates(
                    file_path,
                    candidates,
                    encoding=encoding,
                    batch_size=10
                )
                logger.info("   ✅ [Stage 2 Complete] AI scoring complete")
                reconciliation_log.append("AI 스코어링 완료")
            else:
                logger.warning(f"   ⚠️  [Stage 2 Skipped] Too many candidates ({len(candidates)}), skipping AI scoring")
                reconciliation_log.append(f"AI 스코어링 스킵 (후보 수 과다: {len(candidates)})")
            
            # Stage 3: Topic change detection (if we still need more coverage)
            logger.info("   🔍 [Pipeline Stage 3/5] Topic change detection...")
            if len(candidates) < expected_count * 2:
                logger.info(f"      → Detecting semantic boundaries (need more coverage)")
                topic_candidates = self.topic_detector.detect_topic_boundaries(
                    file_path,
                    expected_count,
                    existing_candidates=candidates,
                    encoding=encoding
                )
                
                if topic_candidates:
                    logger.info(f"   ✅ [Stage 3 Complete] Added {len(topic_candidates)} topic-change candidates")
                    candidates.extend(topic_candidates)
                    reconciliation_log.append(f"토픽 변화 감지: {len(topic_candidates)} 후보 추가")
                else:
                    logger.info("   ℹ️  [Stage 3 Complete] No topic-change candidates found")
            else:
                logger.info(f"   ✅ [Stage 3 Skipped] Sufficient candidates ({len(candidates)} >= {expected_count * 2})")
            
            # Stage 4: Global optimization
            logger.info("   🎯 [Pipeline Stage 4/5] Global optimization...")
            logger.info(f"      → Selecting optimal {expected_count} boundaries from {len(candidates)} candidates")
            selected = self.global_optimizer.select_optimal_boundaries(
                candidates,
                expected_count,
                file_path,
                encoding=encoding,
                anchor_boundaries=anchor_boundaries
            )
            
            if not selected:
                logger.error("   ❌ [Stage 4 Failed] Optimization failed to select boundaries")
                return None
            
            if len(selected) != expected_count:
                logger.warning(f"   ⚠️  [Stage 4 Partial] Optimizer returned {len(selected)}/{expected_count} boundaries")
            else:
                logger.info(f"   ✅ [Stage 4 Complete] Selected exactly {len(selected)} optimal boundaries")
            
            reconciliation_log.append(f"최적화: {len(selected)}개 경계 선택")
            
            # Stage 5: Split using selected boundaries directly (bypass regex patterns)
            logger.info("   📝 [Pipeline Stage 5/5] Splitting chapters using selected boundaries...")
            logger.info(f"      → Boundary count: {len(selected)} (expected: {expected_count})")
            logger.info(f"      → Boundary format: line_num={selected[0]['line_num']}, text='{selected[0]['text'][:20]}...'")
            
            # Validate boundaries before splitting
            if len(selected) != expected_count:
                logger.error(f"   ❌ [Stage 5 Failed] Boundary count mismatch: got {len(selected)}, expected {expected_count}")
                return None
            
            # Validate all boundaries have required fields
            for i, boundary in enumerate(selected):
                if not boundary.get('text', '').strip():
                    logger.error(f"   ❌ [Stage 5 Failed] Boundary {i} has empty text at line {boundary.get('line_num', '?')}")
                    return None
                if 'line_num' not in boundary:
                    logger.error(f"   ❌ [Stage 5 Failed] Boundary {i} missing line_num field")
                    return None
            
            # Use boundary-based split (bypasses regex pattern matching)
            try:
                chapters = list(self.splitter.split_by_boundaries(
                    file_path,
                    selected,
                    encoding=encoding
                ))
            except ValueError as e:
                logger.error(f"   ❌ [Stage 5 Failed] Boundary validation error: {e}")
                return None
            
            # Report creation results
            if len(chapters) == 0:
                logger.error(f"   ❌ [Stage 5 Failed] Created 0 chapters from {len(selected)} boundaries!")
                return None
            elif len(chapters) != len(selected):
                logger.warning(f"   ⚠️  [Stage 5 Partial] Created {len(chapters)}/{len(selected)} chapters")
            else:
                logger.info(f"   ✅ [Stage 5 Complete] Created {len(chapters)} chapters from {len(selected)} boundaries")
            
            # Quality validation: check for too many empty chapters
            if chapters:
                empty_count = sum(1 for ch in chapters if ch.length < self.MIN_VALID_CHAPTER_LENGTH)
                empty_ratio = empty_count / len(chapters)
                if empty_ratio > self.MAX_EMPTY_CHAPTER_RATIO:
                    logger.error(f"   ❌ Quality check FAILED: {empty_count}/{len(chapters)} chapters <{self.MIN_VALID_CHAPTER_LENGTH} chars ({empty_ratio*100:.0f}%)")
                    logger.error(f"   🚫 Advanced pipeline rejected due to too many empty chapters")
                    return None
                
                avg_length = sum(ch.length for ch in chapters) / len(chapters)
                if avg_length < self.MIN_AVG_CHAPTER_LENGTH:
                    logger.error(f"   ❌ Quality check FAILED: avg chapter length = {avg_length:.0f} chars")
                    logger.error(f"   🚫 Advanced pipeline rejected due to low average chapter length")
                    return None
                
                logger.info(f"   ✅ Quality check PASSED: avg length = {avg_length:.0f} chars, empty ratio = {empty_ratio*100:.1f}%")
            
            logger.info("=" * 70)
            logger.info(f"   🎉 ADVANCED PIPELINE COMPLETE: {len(chapters)} chapters extracted")
            logger.info("=" * 70)
            
            return chapters
            
        except Exception as e:
            logger.error("=" * 70)
            logger.error(f"   ❌ ADVANCED ESCALATION PIPELINE FAILED: {e}")
            logger.error("=" * 70)
            traceback.print_exc()
            return None
    
    def _pos_to_line_num(self, file_path: str, pos: int, encoding: str = 'utf-8') -> int:
        """Convert byte position to line number
        
        Args:
            file_path: Path to the file
            pos: Byte position
            encoding: File encoding
            
        Returns:
            Line number (0-indexed) corresponding to the byte position
        """
        try:
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                lines = f.readlines()
            
            current_pos = 0
            for i, line in enumerate(lines):
                line_bytes = len(line.encode(encoding, errors='replace'))
                if current_pos + line_bytes > pos:
                    return i
                current_pos += line_bytes
            
            # If position is beyond file, return last line
            return len(lines) - 1 if lines else 0
            
        except Exception as e:
            logger.warning(f"Could not convert pos to line_num: {e}")
            # Fallback: estimate line number based on average bytes per line
            return pos // self.ESTIMATED_AVG_LINE_BYTES
    
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
    
    def _is_stagnant(self, chapter_count_history: List[int], threshold: int = 3) -> bool:
        """Check if chapter count has stagnated (no meaningful change for N consecutive attempts)
        
        Treats +/-1 or +/-2 fluctuations as stagnant to reliably trigger escalation.
        
        Args:
            chapter_count_history: List of chapter counts from retry attempts
            threshold: Number of consecutive attempts with no meaningful change to consider stagnant
            
        Returns:
            True if stagnated, False otherwise
        """
        if len(chapter_count_history) < threshold:
            return False
        
        recent_counts = chapter_count_history[-threshold:]
        # Check if all counts are within +/-2 of each other (treat as stagnant)
        min_count = min(recent_counts)
        max_count = max(recent_counts)
        return (max_count - min_count) <= 2  # Fluctuations of +/-1 or +/-2 are stagnant

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
