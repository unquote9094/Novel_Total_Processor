"""패턴 관리자 (Reference v3.0 기반 고도화)

AI를 사용하여 소설의 최적 챕터 분할 패턴을 찾아내고 검증
NovelAIze-SSR v3.0의 고품질 프롬프트 복원 및 99% 커버리지 추적 로직 적용
"""

import re
import time
import os
from typing import Optional, Tuple, List, Dict, Any
from novel_total_processor.stages.sampler import Sampler
from novel_total_processor.stages.splitter import Splitter
from novel_total_processor.ai.gemini_client import GeminiClient
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


class PatternManager:
    """AI를 사용하여 소설의 최적 챕터 분할 패턴을 찾아내고 검증 (v3.0 Reference)
    
    Enhanced Features:
    - Dynamic gap detection based on expected chapter count and average size
    - AI-based title candidate extraction with consensus voting
    - Multi-signal recovery for mixed/irregular chapter patterns
    """
    
    def __init__(self, client: GeminiClient):
        self.client = client
        self.splitter = Splitter()
        self.sampler = Sampler()
        self.consensus_votes = 3  # Number of AI calls for consensus voting
    
    def find_best_pattern(
        self,
        target_file: str,
        initial_samples: str,
        filename: Optional[str] = None,
        encoding: str = 'utf-8'
    ) -> Tuple[Optional[str], Optional[str]]:
        """최적의 패턴 탐색 (v3.0 Plan C 정밀 추적 포함)"""
        
        # 1. 기대 화수 추출 (Hotfix v5: 작가명 숫자 오인식 방지)
        expected_count = 0
        if filename:
            # 우선순위 1: 명시적 범위 (예: 1~370화, 1-370)
            range_match = re.search(r'(?:~|-)(\d+)(?:화|회)?', filename)
            if range_match:
                expected_count = int(range_match.group(1))
            else:
                # 우선순위 2: 명시적 총 화수 (예: 총370화, (370화), [370])
                total_match = re.search(r'(?:총|\(|\[)(\d+)(?:화|회|\]|\))', filename)
                if total_match:
                    expected_count = int(total_match.group(1))
                else:
                    # 우선순위 3: 마지막 숫자 (하지만 작가명 등 오인 가능성 있음 -> 보수적 적용)
                    # "burn7" 같은 케이스 방지를 위해, 숫자가 3자리 이상일 때만 신뢰하거나 건너뜀
                    # 여기서는 안전하게 0으로 두고, 명확하지 않으면 AI에 의존하지 않도록 함
                    pass 
            
            if expected_count > 0:
                logger.info(f"   🎯 [Target] 파일명에서 목표 화수 식별: {expected_count}화")

        # 2. AI 분석 (v3.0 원본 프롬프트 사용)
        logger.info(f"   -> 챕터 제목 패턴을 분석 중입니다... (Reference Mode)")
        pattern = self._analyze_pattern_v3(initial_samples)
        
        if not pattern or pattern == "NO_PATTERN_FOUND":
            pattern, _ = self._try_fallback(target_file, encoding=encoding)
            return (pattern, None)

        # 3. 커버리지 검증 및 정밀 추적 (Plan C)
        stats = self.splitter.verify_pattern(target_file, pattern, encoding=encoding)
        
        # v3.0 기준 99% 미달 시 정밀 추적 시작
        if not stats.get('coverage_ok'):
            cur_ratio = stats.get('last_match_ratio', 0)
            logger.warning(f"   ⚠️ 패턴 커버리지 낮음 ({cur_ratio*100:.1f}%). 정밀 추적(Plan C)을 시작합니다.")
            pattern = self._run_adaptive_retry_v3(target_file, pattern, stats, encoding=encoding)
            stats = self.splitter.verify_pattern(target_file, pattern, encoding=encoding)

        # 4. Zero Tolerance (100% 일치 보정)
        if expected_count > 0 and stats.get('match_count', 0) != expected_count:
            logger.info(f"   🔄 [M-45] 화수 정합성 보정 중 ({stats.get('match_count')}/{expected_count})")
            pattern, _ = self.refine_pattern_with_goal_v3(target_file, pattern, expected_count, encoding=encoding)
            
        return (pattern, None)
    

    def _analyze_gap_pattern(self, sample_text: str, current_pattern: str) -> Optional[str]:
        """[Hotfix v7] 누락 구간 전용 정밀 분석 (Context-Aware) + Enhanced with number relaxation"""
        prompt = f"""=== pattern_refinement ===
You are an expert in Regex. We are trying to split a novel into chapters.
We already have a pattern: `{current_pattern}`
However, we missed some chapters in the following text chunk.

[Tasks]
1. Analyze the text and find the Chapter Title pattern used inside this specific chunk.

2. Consider these possibilities:
   - The same format as existing pattern, but WITHOUT number requirements
     (e.g., if current is "< .*?\\(\\d+\\) >", try "< .*? >" for titles without numbers)
   - A slightly different format (e.g., "1화" vs "Chapter 1" vs "Ep.1")
   - Titles that match the visual structure but are missing numbers

3. Create a Python Regex for this pattern.
   - **EXCLUDE end markers**: Lines ending with "끝", "완", "END", "fin", "종료"
   - **DO NOT** return the existing pattern unchanged
   - **DO NOT** match general sentences, dialogue, or page numbers
   - **ONLY** match headlines that look like chapter titles
   - Make number patterns OPTIONAL with \\d* instead of \\d+ if titles vary

[Current Pattern]
{current_pattern}

[Text Chunk (Missed Area)]
{sample_text[:30000]}

[Output]
Return ONLY the raw Regex string. No markdown, no explanations.
"""
        return self._generate_regex_from_ai(prompt)

    def _analyze_pattern_v3(self, sample_text: str) -> Optional[str]:
        """NovelAIze-SSR v3.0 원본 프롬프트 복원 + Enhanced with Korean novel patterns"""
        prompt = f"""=== pattern_analysis ===
You are an expert in Regex (Regular Expressions) and Text Analysis.
Analyze the following Novel Text Samples and identify the Pattern used for Chapter Titles.

[Common Korean Novel Chapter Formats]
Examples of real chapter title patterns used in Korean novels:
- Numbered: "N화", "제N화", "N회", "제N장", "Chapter N", "Ep.N", "Episode N", "N話", "第N話"
- Bracketed: "< 제목 >", "【 제목 】", "[ 제목 ]", "[N화]", "<N화>"
- Decorated: "― 제목 ―", "★ 제목", "◆ 제목 ◆", "■ 제목", "▣ N화"
- Special: "프롤로그", "에필로그", "외전", "번외", "후기", "작가의 말"
- Mixed: Some chapters may have numbers, others may not (e.g., "< 에피소드(3) >" and "< 연습생 면접 >")

[CRITICAL WARNINGS]
1. **START vs END Markers**: 
   - Some novels use PAIRED structures: "< 제목 >" (START) and "< 제목 > 끝" (END)
   - Your regex MUST match ONLY the START markers
   - **EXCLUDE** any lines ending with: "끝", "완", "END", "fin", "종료", "끗", "end", "完"
   - Use negative lookahead if needed: (?!.*끝\\s*$)

2. **Number Flexibility**:
   - Numbers may be OPTIONAL in titles
   - Some chapters have numbers ("< 에피소드(3) >"), others don't ("< 연습생 면접 >")
   - Do NOT require \\d+ if the pattern works without it

3. **Pattern Precision**:
   - Match complete title lines, not just fragments
   - Avoid matching dialogue, body text, or page numbers
   - Look for consistent formatting (brackets, spacing, decoration)

[Tasks]
1. Find all consistent patterns that denote a new chapter START.
   **CRITICAL: Detect Mixed or Inconsistent patterns.**
   If the novel uses multiple formats (e.g., some use "1화", others use "Chapter 1"), identify ALL of them.

2. Create a Python Compatible Regular Expression (Regex) to match these chapter START titles.
   - Use the `|` (OR) operator to combine multiple patterns if necessary.
   - Use `\\s*` for flexible whitespace and `\\d*` or `\\d+` for numbers (make optional if needed).
   - **MUST exclude end markers** (lines ending with "끝", "완", "END", etc.)

3. OUTPUT ONLY the raw Regex string. No markdown, no explanations.
   - If no pattern found, return "NO_PATTERN_FOUND".

[Novel Text Samples]
{sample_text[:30000]}
"""
        return self._generate_regex_from_ai(prompt)

    def _generate_regex_from_ai(self, prompt: str) -> Optional[str]:
        """AI 응답 처리 공통 로직"""
        try:
            response = self.client.generate_content(prompt)
            
            # Fix #2: Check for None or empty response before calling .strip()
            if response is None or not response:
                logger.warning("   ⚠️  AI returned None or empty response, skipping")
                return None
            
            # 마크다운 및 불필요 텍스트 정제
            result = response.strip().replace("```python", "").replace("```re", "").replace("```", "").replace("r'", "").replace("'", "").strip()
            if "NO_PATTERN_FOUND" in result: return None
            # 줄바꿈이 있는 경우 첫 줄만 사용
            result = result.splitlines()[0] if result else None
            
            # Fix #3: Enhanced regex validation and sanitization
            if result:
                # Validate pattern: reject leading '?' or other invalid patterns
                if result.startswith('?'):
                    logger.warning(f"   ⚠️  Rejecting invalid pattern (starts with '?'): {result}")
                    return None
                
                # Check for properly matched parentheses and valid named groups
                # Count opening and closing parentheses
                open_parens = result.count('(')
                close_parens = result.count(')')
                if open_parens != close_parens:
                    logger.warning(f"   ⚠️  Rejecting pattern with mismatched parentheses: {result}")
                    return None
                
                try:
                    re.compile(result)
                except re.error as e:
                    logger.error(f"   ❌ AI 생성 정규식 오류: {e} (Pattern: {result})")
                    return None
            return result
        except Exception as e:
            logger.error(f"   ❌ AI 분석 중 에러: {e}")
            return None

    def _run_adaptive_retry_v3(self, target_file: str, current_pattern: str, verify_stats: dict, encoding: str = 'utf-8') -> str:
        """v3.0 정밀 추적 로직 (최대 10회)"""
        retry_count = 0
        max_retries = 3
        pattern = current_pattern
        stats = verify_stats
        
        while not stats['coverage_ok'] and retry_count < max_retries:
            retry_count += 1
            fail_pos = stats['last_match_pos']
            
            # 실패 지점부터 다시 샘플링
            retry_sample = self.sampler.extract_samples_from(target_file, fail_pos, length=30000, encoding=encoding)
            if not retry_sample: break
                
            logger.info(f"   🔄 [Retry {retry_count}/{max_retries}] 누락 지점({fail_pos}) 분석 중...")
            new_pattern = self._analyze_pattern_v3(retry_sample)
            
            if new_pattern and new_pattern != "NO_PATTERN_FOUND":
                combined_pattern = f"{pattern}|{new_pattern}"
                new_stats = self.splitter.verify_pattern(target_file, combined_pattern, encoding=encoding)
                
                # 조금이라도 나아지면 적용
                new_ratio = new_stats.get('last_match_ratio', 0)
                old_ratio = stats.get('last_match_ratio', 0)
                new_tail = new_stats.get('tail_size', 9999999)
                old_tail = stats.get('tail_size', 9999999)

                if new_ratio > old_ratio or new_tail < old_tail:
                    pattern = combined_pattern
                    stats = new_stats
                    if stats.get('coverage_ok'):
                        logger.info(f"   ✨ [Plan C Success] 목표 커버리지 달성!")
                        break
                else:
                    logger.info("   ❌ 개선되지 않음. 다음 단계 진행...")
            else:
                break
        return pattern

    def refine_pattern_with_goal_v3(self, target_file: str, current_pattern: str, expected_count: int, encoding: str = 'utf-8', max_gaps: int = 3) -> Tuple[str, int]:
        """100% 일치를 위한 최종 보정 (v3.0 확장) - 3-Level Escalation
        
        Level 1: AI regex generation (already done by caller)
        Level 2: Code-level auto validation and fixing
        Level 3: Direct AI title search in gaps (if Level 1+2 < 95%)
        
        Args:
            target_file: Target file path
            current_pattern: Current regex pattern
            expected_count: Expected number of chapters
            encoding: File encoding
            max_gaps: Maximum number of gaps to analyze (default: 3) to cap AI calls
            
        Returns:
            Tuple of (refined_pattern, rejection_count)
        """
        matches = self.splitter.find_matches_with_pos(target_file, current_pattern, encoding=encoding)
        actual_count = len(matches)
        
        if actual_count == expected_count: 
            return (current_pattern, 0)
        
        # Level 2: Auto-validation and fixing (before AI pattern refinement)
        if expected_count > 0 and actual_count != expected_count:
            logger.info(f"   🔧 Applying Level 2 auto-validation...")
            auto_fixed_pattern, auto_count = self.auto_validate_and_fix(
                target_file, current_pattern, expected_count, encoding
            )
            
            # If auto-fix achieved the goal, return immediately
            if auto_count == expected_count:
                logger.info(f"   ✅ [Level 2 Success] Auto-fix achieved target: {auto_count}/{expected_count}")
                return (auto_fixed_pattern, 0)
            
            # If auto-fix improved significantly, use it as the new baseline
            if auto_count > actual_count:
                logger.info(f"   ✨ [Level 2 Improved] Using auto-fixed pattern: {actual_count} -> {auto_count}")
                current_pattern = auto_fixed_pattern
                actual_count = auto_count
                matches = self.splitter.find_matches_with_pos(target_file, current_pattern, encoding=encoding)
        
        # 과매칭 시: 숫자 시퀀스 필터링 강화
        if actual_count > expected_count:
            logger.info(f"   🔄 과매칭 제거 시도 ({actual_count}ch -> {expected_count}ch)")
            # 가장 확실한 숫자 패턴들 시도
            for ptn in [r"(?:제\s*)?\d+\s*화", r"\d+\s*화", r"\[\d+\]", r"Chapter\s*\d+"]:
                s = self.splitter.verify_pattern(target_file, ptn, encoding=encoding)
                if s['match_count'] == expected_count: 
                    return (ptn, 0)
        
        # 부족 시: 동적 갭 분석 및 타이틀 후보 탐지
        if actual_count < expected_count:
            missing_count = expected_count - actual_count
            logger.info(f"   🔄 부족 화수 추적 중 (누락: {missing_count}개)")
            
            # Use dynamic gap detection
            gaps = self.find_dynamic_gaps(target_file, matches, expected_count)
            
            # Limit gaps to max_gaps to cap AI calls
            limited_gaps = gaps[:max_gaps]
            logger.info(f"   📊 Gap 분석 제한: {len(limited_gaps)}/{len(gaps)} gaps (MAX_GAPS_TO_ANALYZE={max_gaps})")
            
            # [Hotfix v4] 화수 퇴보 방지 (Strict Improvement Rule)
            best_pattern = current_pattern
            best_count = actual_count
            
            # Track title candidates for fallback and rejection count
            all_title_candidates = []
            rejection_count = 0
            
            for gap in limited_gaps:
                sample = self.sampler.extract_samples_from(target_file, gap['start'], length=30000, encoding=encoding)
                if not sample: continue
                
                # Try pattern refinement first
                new_p = self._analyze_gap_pattern(sample, best_pattern)
                if new_p:
                    test_p = f"{best_pattern}|{new_p}"
                    test_s = self.splitter.verify_pattern(target_file, test_p, encoding=encoding)
                    new_count = test_s.get('match_count', 0)
                    
                    # 1. 화수가 기존보다 늘어났고 2. 목표치를 넘지 않을 때만 수용
                    if new_count > best_count and new_count <= expected_count:
                        logger.info(f"   ✨ 패턴 보강 성공: {best_count}화 -> {new_count}화")
                        best_pattern = test_p
                        best_count = new_count
                        rejection_count = 0  # Reset rejection count on success
                        if best_count == expected_count: break
                    else:
                        rejection_count += 1
                        logger.info(f"   ❌ 보강 패턴 거절 (화수 변화: {best_count} -> {new_count}, 연속 거절: {rejection_count})")
                
                # If pattern didn't work, try title candidate extraction
                if best_count < expected_count:
                    candidates = self.extract_title_candidates(sample, best_pattern)
                    all_title_candidates.extend(candidates)
            
            # If we still have missing chapters and found title candidates, log them
            if best_count < expected_count and all_title_candidates:
                logger.info(f"   📝 Found {len(all_title_candidates)} title candidates for manual/fallback processing")
                # Store candidates for later use by stage4_splitter
                # We'll pass this information back through the pattern
                # For now, just use the improved pattern
            
            # Level 3: Direct AI title search if still below 95% accuracy
            if best_count < expected_count * 0.95:
                logger.info(f"   🚀 [Level 3 Trigger] Current accuracy: {best_count}/{expected_count} ({best_count/expected_count*100:.1f}%)")
                logger.info(f"   -> Activating Level 3: Direct AI title search...")
                
                # Get existing matches with text for context
                existing_matches = self._find_matches_with_text(target_file, best_pattern, encoding)
                
                # Call Level 3 direct search
                found_titles = self.direct_ai_title_search(
                    target_file, best_pattern, expected_count, existing_matches, encoding
                )
                
                if found_titles:
                    logger.info(f"   ✨ [Level 3] Found {len(found_titles)} additional titles via AI search")
                    
                    # Build pattern from these examples
                    reverse_pattern = self._build_pattern_from_examples(found_titles)
                    
                    if reverse_pattern:
                        # Combine with existing pattern
                        combined = f"{best_pattern}|{reverse_pattern}"
                        
                        # Test the combined pattern
                        test_s = self.splitter.verify_pattern(target_file, combined, encoding=encoding)
                        new_count = test_s.get('match_count', 0)
                        
                        # Accept if it improves and doesn't over-match (within 5% tolerance)
                        if new_count > best_count and new_count <= expected_count * 1.05:
                            logger.info(f"   ✅ [Level 3 Success] Pattern improved: {best_count} -> {new_count}")
                            best_pattern = combined
                            best_count = new_count
                        else:
                            logger.info(f"   ❌ [Level 3] Reverse pattern didn't improve ({new_count} matches)")
                    else:
                        logger.warning(f"   ⚠️  [Level 3] Failed to build reverse pattern from examples")
                else:
                    logger.info(f"   ℹ️  [Level 3] No additional titles found by AI")
            
            return (best_pattern, rejection_count)

        return (current_pattern, 0)

    def find_dynamic_gaps(self, target_file: str, matches: list, expected_count: int) -> list:
        """Dynamic gap detection based on average chapter size and expected count
        
        Uses adaptive thresholds instead of fixed 100KB gaps. The threshold is calculated
        as 1.5x the average chapter size to account for novels with varying chapter lengths.
        
        Args:
            target_file: Path to the file
            matches: List of match positions
            expected_count: Expected number of chapters
            
        Returns:
            List of gap dictionaries with start, end, size, and priority
        """
        if not matches or expected_count <= 0:
            return []
        
        total_size = os.path.getsize(target_file)
        
        # Calculate average expected chapter size
        avg_chapter_size = total_size / expected_count if expected_count > 0 else 100000
        
        # Dynamic threshold constants
        GAP_MULTIPLIER = 1.5  # Gaps must be 1.5x average to be significant
        MIN_GAP_SIZE = 50000  # Minimum 50KB regardless of average (prevents tiny gaps)
        
        # Dynamic threshold: gaps larger than 1.5x average chapter size
        dynamic_threshold = max(avg_chapter_size * GAP_MULTIPLIER, MIN_GAP_SIZE)
        
        gaps = []
        
        # Check gap before first match
        if matches[0]['pos'] > dynamic_threshold:
            gaps.append({
                'start': 0,
                'end': matches[0]['pos'],
                'size': matches[0]['pos'],
                'priority': matches[0]['pos'] / avg_chapter_size
            })
        
        # Check gaps between matches
        for i in range(len(matches) - 1):
            gap_size = matches[i + 1]['pos'] - matches[i]['pos']
            if gap_size > dynamic_threshold:
                gaps.append({
                    'start': matches[i]['pos'],
                    'end': matches[i + 1]['pos'],
                    'size': gap_size,
                    'priority': gap_size / avg_chapter_size
                })
        
        # Check gap after last match
        tail_size = total_size - matches[-1]['pos']
        if tail_size > dynamic_threshold:
            gaps.append({
                'start': matches[-1]['pos'],
                'end': total_size,
                'size': tail_size,
                'priority': tail_size / avg_chapter_size
            })
        
        # Sort by priority (largest gaps relative to average first)
        gaps.sort(key=lambda x: x['priority'], reverse=True)
        
        logger.info(f"   📊 Dynamic gap analysis: {len(gaps)} gaps found (threshold: {dynamic_threshold/1024:.1f}KB)")
        
        return gaps[:10]  # Return top 10 gaps

    def extract_title_candidates(self, window_text: str, current_pattern: str) -> List[str]:
        """AI-based title candidate extraction for a specific window
        
        Uses consensus voting across multiple AI calls for robustness.
        
        Args:
            window_text: Text window to analyze
            current_pattern: Current regex pattern (for context)
            
        Returns:
            List of title candidate lines
        """
        prompt = f"""=== title_candidate_extraction ===
You are an expert in analyzing novel text structures.

[Task]
Find all lines that could be chapter titles in the following text.
Return ONLY the actual title lines, one per line, nothing else.

A chapter title is:
- Usually short (1-50 characters)
- May or may not contain numbers (both are valid)
- May contain episode markers or chapter indicators
- Stands out from regular narrative text
- May use brackets, special formatting, or numbering
- Examples: "< 제목 >", "제3화", "Chapter 5", "프롤로그", "에필로그(1)"

**IMPORTANT**: 
- Titles WITHOUT numbers are equally valid as titles WITH numbers
- DO NOT exclude titles just because they lack numbers
- EXCLUDE lines ending with "끝", "완", "END", "fin" (these are END markers, not titles)

[Current Pattern Context]
We already found some chapters with pattern: {current_pattern}
But we're missing chapters in this specific area.

[Text Window]
{window_text[:20000]}

[Output Format]
Return only the title lines, one per line. No explanations, no markdown.
If no titles found, return "NO_TITLES_FOUND".
"""
        
        all_candidates = []
        
        # Consensus voting: call AI multiple times
        for vote in range(self.consensus_votes):
            try:
                response = self.client.generate_content(prompt)
                if response and "NO_TITLES_FOUND" not in response:
                    lines = [line.strip() for line in response.strip().split('\n') if line.strip()]
                    all_candidates.extend(lines)
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                logger.warning(f"   ⚠️ Title candidate extraction vote {vote+1} failed: {e}")
        
        # Count occurrences of each candidate (consensus filtering)
        from collections import Counter
        candidate_counts = Counter(all_candidates)
        
        # Majority voting: Keep candidates that appear in at least half the votes (rounded up)
        # This implements a simple consensus mechanism for robustness
        CONSENSUS_THRESHOLD_RATIO = 0.5  # Require at least 50% agreement
        consensus_threshold = max(1, int(self.consensus_votes * CONSENSUS_THRESHOLD_RATIO))
        
        consensus_candidates = [
            candidate for candidate, count in candidate_counts.items()
            if count >= consensus_threshold
        ]
        
        logger.info(f"   📋 Title candidates: {len(consensus_candidates)} found via consensus")
        
        return consensus_candidates

    def auto_validate_and_fix(
        self, 
        target_file: str, 
        current_pattern: str, 
        expected_count: int,
        encoding: str = 'utf-8'
    ) -> Tuple[str, int]:
        """Level 2: Code-level automatic validation and fixing (no AI calls)
        
        Automatically detects and fixes common pattern issues:
        1. End marker contamination (lines ending with "끝", "완", "END", etc.)
        2. Close duplicate matches (start/end pairs too close together)
        3. Number requirement relaxation (remove \\d+ to match unnumbered titles)
        4. Negative lookahead for end marker exclusion
        
        Args:
            target_file: Path to target file
            current_pattern: Current regex pattern
            expected_count: Expected number of chapters
            encoding: File encoding
            
        Returns:
            Tuple of (cleaned_pattern, match_count)
        """
        logger.info("   🔧 [Level 2] Auto-validation and fixing pattern...")
        
        # Get initial matches with their text content
        matches = self._find_matches_with_text(target_file, current_pattern, encoding)
        initial_count = len(matches)
        
        logger.info(f"   📊 Initial matches: {initial_count}")
        
        # Step 1: Detect and separate end markers
        end_keywords = ['끝', '완', 'END', 'end', 'fin', 'Fin', '종료', '끗', '完']
        start_matches, end_matches = self._separate_start_end_matches(matches, end_keywords)
        
        if end_matches:
            logger.info(f"   ⚠️  Detected {len(end_matches)} end markers in matches")
            logger.info(f"   ✂️  Removed end markers: {initial_count} -> {len(start_matches)} matches")
            matches = start_matches
        
        # Step 2: Remove close duplicates (likely start/end pairs)
        MIN_GAP = 500  # Minimum 500 chars between chapter starts
        cleaned_matches = self._remove_close_duplicates(matches, MIN_GAP)
        
        if len(cleaned_matches) < len(matches):
            logger.info(f"   🔍 Removed {len(matches) - len(cleaned_matches)} close duplicates")
            matches = cleaned_matches
        
        current_count = len(matches)
        logger.info(f"   📊 After cleanup: {current_count} matches")
        
        # Step 3: If still under 95% of expected, try relaxing number requirements
        if expected_count > 0 and current_count < expected_count * 0.95:
            relaxed_pattern = self._relax_number_requirement(current_pattern)
            
            if relaxed_pattern != current_pattern:
                logger.info(f"   🔄 Trying relaxed pattern (numbers optional)...")
                logger.info(f"   Old: {current_pattern}")
                logger.info(f"   New: {relaxed_pattern}")
                
                # Test relaxed pattern
                relaxed_matches = self._find_matches_with_text(target_file, relaxed_pattern, encoding)
                # Clean end markers again
                relaxed_matches, _ = self._separate_start_end_matches(relaxed_matches, end_keywords)
                relaxed_matches = self._remove_close_duplicates(relaxed_matches, MIN_GAP)
                
                relaxed_count = len(relaxed_matches)
                logger.info(f"   📊 Relaxed pattern matches: {relaxed_count}")
                
                # Accept if improved and not over-matching (with 5% tolerance)
                if relaxed_count > current_count and relaxed_count <= expected_count * 1.05:
                    logger.info(f"   ✅ Relaxed pattern accepted: {current_count} -> {relaxed_count}")
                    current_pattern = relaxed_pattern
                    current_count = relaxed_count
                else:
                    logger.info(f"   ❌ Relaxed pattern rejected (over-match or no improvement)")
        
        # Step 4: Add negative lookahead for end markers if not present
        if any(keyword in current_pattern for keyword in end_keywords):
            # Pattern already has end marker logic, skip
            pass
        else:
            # Add negative lookahead to exclude end markers
            enhanced_pattern = self._add_end_marker_exclusion(current_pattern, end_keywords)
            if enhanced_pattern != current_pattern:
                logger.info(f"   🛡️  Added end marker exclusion to pattern")
                current_pattern = enhanced_pattern
        
        logger.info(f"   ✅ [Level 2] Auto-validation complete: {current_count} matches")
        
        return current_pattern, current_count
    
    def _find_matches_with_text(self, target_file: str, pattern: str, encoding: str) -> List[Dict[str, Any]]:
        """Find pattern matches with their text content"""
        matches = []
        try:
            compiled_pattern = re.compile(pattern)
            with open(target_file, 'r', encoding=encoding, errors='replace') as f:
                pos = 0
                for line_num, line in enumerate(f):
                    if compiled_pattern.search(line.strip()):
                        matches.append({
                            'pos': pos,
                            'line_num': line_num,
                            'text': line.strip()
                        })
                    pos += len(line.encode(encoding, errors='replace'))
        except Exception as e:
            logger.warning(f"   ⚠️  Error finding matches: {e}")
        
        return matches
    
    def _separate_start_end_matches(
        self, 
        matches: List[Dict[str, Any]], 
        end_keywords: List[str]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Separate start markers from end markers"""
        start_matches = []
        end_matches = []
        
        for match in matches:
            text = match['text']
            # Check if line ends with any end keyword
            is_end = False
            for keyword in end_keywords:
                # Check for keyword at end of line (with optional whitespace/punctuation)
                if re.search(rf'{keyword}\s*[>】\])\)]*\s*$', text):
                    is_end = True
                    break
            
            if is_end:
                end_matches.append(match)
            else:
                start_matches.append(match)
        
        return start_matches, end_matches
    
    def _remove_close_duplicates(
        self, 
        matches: List[Dict[str, Any]], 
        min_gap: int
    ) -> List[Dict[str, Any]]:
        """Remove matches that are too close together (likely start/end pairs)"""
        if not matches:
            return matches
        
        cleaned = [matches[0]]  # Keep first match
        
        for i in range(1, len(matches)):
            gap = matches[i]['pos'] - matches[i-1]['pos']
            if gap >= min_gap:
                cleaned.append(matches[i])
            else:
                logger.debug(f"   Removing close duplicate: '{matches[i]['text']}' (gap: {gap} chars)")
        
        return cleaned
    
    def _relax_number_requirement(self, pattern: str) -> str:
        """Relax number requirements in pattern with multiple strategies
        
        Strategy 1: \\d+ -> \\d* (make numbers optional)
        Strategy 2: \\(\\d+\\) or \\(\\d*\\) -> (?:\\(\\d*\\))? (make entire parenthesized number optional)
        Strategy 3: Remove number requirements entirely, keeping only structure
        
        Returns the best variation based on testing
        """
        variations = []
        
        # Strategy 1: \\d+ -> \\d* (original approach)
        v1 = pattern.replace(r'\d+', r'\d*')
        if v1 != pattern:
            variations.append(('strategy1_digit_optional', v1))
        
        # Strategy 2: Make parenthesized numbers completely optional
        # Match patterns like \\(\\d+\\) or \\(\\d*\\) and make them optional
        v2 = re.sub(r'\\?\(\\d[+*]\\?\)', r'(?:\\(\\d*\\))?', pattern)
        if v2 != pattern:
            variations.append(('strategy2_parens_optional', v2))
        
        # Strategy 3: Combine both strategies
        v3 = re.sub(r'\\?\(\\d[+*]\\?\)', r'(?:\\(\\d*\\))?', v1)
        if v3 != pattern and v3 != v1 and v3 != v2:
            variations.append(('strategy3_combined', v3))
        
        # If no variations were created, return original
        if not variations:
            return pattern
        
        # Log the variations for debugging
        logger.info(f"   🔄 Generated {len(variations)} relaxation variations:")
        for name, var_pattern in variations:
            logger.info(f"      - {name}: {var_pattern[:80]}{'...' if len(var_pattern) > 80 else ''}")
        
        # Return the most aggressive variation (strategy 3 if available, else strategy 2, else strategy 1)
        # This gives the best chance to match titles without numbers or parentheses
        return variations[-1][1] if variations else pattern
    
    def _add_end_marker_exclusion(self, pattern: str, end_keywords: List[str]) -> str:
        """Add negative lookahead to exclude end markers"""
        # Create a negative lookahead pattern for all end keywords
        # Pattern: (?!.*(?:끝|완|END|fin)\\s*$)
        
        exclusion_pattern = '|'.join(re.escape(kw) for kw in end_keywords)
        negative_lookahead = f'(?!.*(?:{exclusion_pattern})\\s*[>】\\])\\)]*\\s*$)'
        
        # Add at the beginning of the pattern if not already present
        if '(?!' not in pattern:
            enhanced = negative_lookahead + pattern
            return enhanced
        
        return pattern
    
    def direct_ai_title_search(
        self,
        target_file: str,
        current_pattern: str,
        expected_count: int,
        existing_matches: List[Dict[str, Any]],
        encoding: str = 'utf-8'
    ) -> List[str]:
        """Level 3: Direct AI title search using 30 samples
        
        When Level 1 (regex) and Level 2 (auto-fix) don't achieve 95% accuracy,
        ask AI to directly find chapter titles by examining 30 evenly distributed samples
        from the entire file.
        
        Args:
            target_file: Path to target file
            current_pattern: Current pattern (for context)
            expected_count: Expected number of chapters
            existing_matches: Already found matches with position and text
            encoding: File encoding
            
        Returns:
            List of title lines found by AI
        """
        logger.info("   🔍 [Level 3] Direct AI title search using 30 samples...")
        
        # Get examples of existing titles for context
        example_titles = [m['text'] for m in existing_matches[:10]]
        
        # Extract 30 samples from the entire file (not just gaps)
        logger.info(f"   📊 Extracting 30 samples from file for comprehensive search...")
        samples_text = self.sampler.extract_samples(target_file, encoding=encoding)
        
        if not samples_text:
            logger.warning("   ⚠️  Failed to extract samples")
            return []
        
        all_found_titles = []
        
        # Split samples into manageable chunks for AI processing
        # Each chunk should be around 20000 chars to fit in AI context
        MAX_CHUNK_SIZE = 20000
        chunks = []
        current_chunk = ""
        
        for line in samples_text.split('\n'):
            if len(current_chunk) + len(line) + 1 > MAX_CHUNK_SIZE:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line + '\n'
            else:
                current_chunk += line + '\n'
        
        if current_chunk:
            chunks.append(current_chunk)
        
        logger.info(f"   📦 Split samples into {len(chunks)} chunks for AI processing")
        
        # Process each chunk
        for i, chunk_text in enumerate(chunks):
            logger.info(f"   🔎 Processing chunk {i+1}/{len(chunks)} ({len(chunk_text)} chars)")
            
            # Ask AI to find titles directly
            prompt = f"""=== direct_title_search ===
You are an expert in Korean novel structure analysis.

[Task]
Find ALL chapter title lines in the text below.
Look at the examples and find similar titles in the text.

[Examples of Chapter Titles Already Found]
{chr(10).join(f'- {title}' for title in example_titles) if example_titles else '(No examples yet - find chapter title patterns)'}

[Instructions]
1. Find lines with the SAME format/structure as the examples (or similar patterns if no examples)
2. Include titles WITH numbers and WITHOUT numbers (both are valid)
3. EXCLUDE lines ending with "끝", "완", "END", "fin" (end markers)
4. EXCLUDE dialogue, body text, and page numbers
5. Return ONLY the actual title lines found

[Text to Search]
{chunk_text}

[Output]
List each found title on a separate line.
If no titles found, return "NO_TITLES_FOUND".
"""
            
            try:
                response = self.client.generate_content(prompt)
                if response and "NO_TITLES_FOUND" not in response:
                    found = [line.strip() for line in response.strip().split('\n') 
                            if line.strip() and len(line.strip()) < 100]
                    
                    if found:
                        logger.info(f"   ✨ Found {len(found)} titles in chunk {i+1}: {found[:3]}...")
                        all_found_titles.extend(found)
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"   ⚠️  Direct search in chunk {i+1} failed: {e}")
        
        # Remove duplicates while preserving order
        unique_titles = []
        seen = set()
        for title in all_found_titles:
            normalized = title.strip()
            if normalized not in seen:
                seen.add(normalized)
                unique_titles.append(title)
        
        logger.info(f"   📝 [Level 3] Total unique titles found: {len(unique_titles)} (from {len(all_found_titles)} total)")
        
        return unique_titles
    
    def _build_pattern_from_examples(self, title_examples: List[str]) -> Optional[str]:
        """Build regex pattern from actual title examples (reverse extraction)
        
        Takes a list of actual chapter title lines found by AI and asks AI to
        generate a regex pattern that matches all of them.
        
        Args:
            title_examples: List of actual title lines found
            
        Returns:
            Regex pattern string or None if failed
        """
        if not title_examples:
            logger.warning("   ⚠️  No title examples provided for reverse pattern extraction")
            return None
        
        logger.info(f"   🔄 [Reverse Extraction] Building pattern from {len(title_examples)} examples...")
        
        # Limit to 30 examples to keep prompt size reasonable
        sample_titles = title_examples[:30]
        
        prompt = f"""=== reverse_pattern_extraction ===
You are a regex expert specialized in Korean novel chapter title patterns.

Below are ACTUAL chapter title lines found in a Korean novel.
Create a Python regex pattern that matches ALL of these titles.

[Title Examples]
{chr(10).join(f'- {t}' for t in sample_titles)}

[Rules]
- The regex must match ALL examples above
- EXCLUDE lines ending with "끝", "완", "END", "fin" (end markers)
- Use negative lookahead if needed: (?!.*끝\\s*$)
- Keep the pattern as precise as possible to avoid false matches
- The pattern should generalize to similar titles (not just literal matches)
- Use character classes, quantifiers, and groups appropriately

[Output Format]
Output ONLY the raw regex pattern. No markdown, no explanation, no code blocks.
Just the regex string itself.

Example output format: ^\\s*<\\s*.+?\\s*>\\s*$
"""
        
        try:
            response = self.client.generate_content(prompt)
            if response:
                # Clean up the response (remove markdown, extra whitespace)
                pattern = response.strip()
                
                # Remove markdown code blocks if present
                if pattern.startswith('```'):
                    lines = pattern.split('\n')
                    pattern = '\n'.join(l for l in lines if not l.startswith('```'))
                    pattern = pattern.strip()
                
                # Validate it's a valid regex
                try:
                    re.compile(pattern)
                    logger.info(f"   ✅ [Reverse Extraction] Generated pattern: {pattern[:80]}{'...' if len(pattern) > 80 else ''}")
                    return pattern
                except re.error as e:
                    logger.error(f"   ❌ [Reverse Extraction] Invalid regex generated: {e}")
                    return None
            
        except Exception as e:
            logger.error(f"   ❌ [Reverse Extraction] Failed to generate pattern: {e}")
        
        return None
    
    def _try_fallback(self, target_file: str, encoding: str = 'utf-8') -> Tuple[Optional[str], Optional[str]]:
        for ptn in [r"\d+\s*화", r"제\s*\d+\s*화", r"\[\d+\]"]:
            stats = self.splitter.verify_pattern(target_file, ptn, encoding=encoding)
            if stats['match_count'] > 0: return (ptn, None)
        return (None, None)
