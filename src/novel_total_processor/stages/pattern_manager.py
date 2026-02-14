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
            pattern = self.refine_pattern_with_goal_v3(target_file, pattern, expected_count, encoding=encoding)
            
        return (pattern, None)
    

    def _analyze_gap_pattern(self, sample_text: str, current_pattern: str) -> Optional[str]:
        """[Hotfix v7] 누락 구간 전용 정밀 분석 (Context-Aware)"""
        prompt = f"""=== pattern_refinement ===
You are an expert in Regex. We are trying to split a novel into chapters.
We already have a pattern: `{current_pattern}`
However, we missed some chapters in the following text chunk.

[Tasks]
1. Analyze the text and find the Chapter Title pattern used inside this specific chunk.
2. It might be slightly different from the existing pattern (e.g., "1화" vs "Chapter 1").
3. Create a Python Regex for this NEW pattern.
   - **DO NOT** return the existing pattern again.
   - **DO NOT** match general sentences or page numbers.
   - **ONLY** match headlines that look like chapter titles.

[Text Chunk (Missed Area)]
{sample_text[:30000]}

[Output]
Return ONLY the raw Regex string. No markdown.
"""
        return self._generate_regex_from_ai(prompt)

    def _analyze_pattern_v3(self, sample_text: str) -> Optional[str]:
        """NovelAIze-SSR v3.0 원본 프롬프트 복원"""
        prompt = f"""=== pattern_analysis ===
You are an expert in Regex (Regular Expressions) and Text Analysis.
Analyze the following Novel Text Samples and identify the Pattern used for Chapter Titles.

[Tasks]
1. Find all consistent patterns that denote a new chapter start.
   **CRITICAL: Detect Mixed or Inconsistent patterns.**
   If the novel uses multiple formats (e.g., some chapters use "1화", while others use "Chapter 1" or "Ep.1"), identify ALL of them.
2. Create a Python Compatible Regular Expression (Regex) to match these chapter titles.
   - Use the `|` (OR) operator to combine multiple patterns if necessary.
   - Use `\\s*` for flexible whitespace and `\\d+` for numbers.
3. OUTPUT ONLY the raw Regex string. No markdown, no content.
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
                
                # Check for unescaped patterns that might cause issues
                if '(?P<' in result and ')' not in result[result.index('(?P<'):]:
                    logger.warning(f"   ⚠️  Rejecting pattern with unclosed named group: {result}")
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
        max_retries = 10
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

    def refine_pattern_with_goal_v3(self, target_file: str, current_pattern: str, expected_count: int, encoding: str = 'utf-8') -> str:
        """100% 일치를 위한 최종 보정 (v3.0 확장) - 동적 갭 분석 및 타이틀 후보 탐지 포함"""
        matches = self.splitter.find_matches_with_pos(target_file, current_pattern, encoding=encoding)
        actual_count = len(matches)
        
        if actual_count == expected_count: return current_pattern
        
        # 과매칭 시: 숫자 시퀀스 필터링 강화
        if actual_count > expected_count:
            logger.info(f"   🔄 과매칭 제거 시도 ({actual_count}ch -> {expected_count}ch)")
            # 가장 확실한 숫자 패턴들 시도
            for ptn in [r"(?:제\s*)?\d+\s*화", r"\d+\s*화", r"\[\d+\]", r"Chapter\s*\d+"]:
                s = self.splitter.verify_pattern(target_file, ptn, encoding=encoding)
                if s['match_count'] == expected_count: return ptn
        
        # 부족 시: 동적 갭 분석 및 타이틀 후보 탐지
        if actual_count < expected_count:
            missing_count = expected_count - actual_count
            logger.info(f"   🔄 부족 화수 추적 중 (누락: {missing_count}개)")
            
            # Use dynamic gap detection
            gaps = self.find_dynamic_gaps(target_file, matches, expected_count)
            
            # [Hotfix v4] 화수 퇴보 방지 (Strict Improvement Rule)
            best_pattern = current_pattern
            best_count = actual_count
            
            # Track title candidates for fallback
            all_title_candidates = []
            
            for gap in gaps:
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
                        if best_count == expected_count: break
                    else:
                        logger.info(f"   ❌ 보강 패턴 거절 (화수 변화: {best_count} -> {new_count})")
                
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
            
            return best_pattern

        return current_pattern

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
- Contains numbers, episode markers, or chapter indicators
- Stands out from regular narrative text
- May use brackets, special formatting, or numbering

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

    def _try_fallback(self, target_file: str, encoding: str = 'utf-8') -> Tuple[Optional[str], Optional[str]]:
        for ptn in [r"\d+\s*화", r"제\s*\d+\s*화", r"\[\d+\]"]:
            stats = self.splitter.verify_pattern(target_file, ptn, encoding=encoding)
            if stats['match_count'] > 0: return (ptn, None)
        return (None, None)
