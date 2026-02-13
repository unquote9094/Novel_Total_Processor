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
    """AI를 사용하여 소설의 최적 챕터 분할 패턴을 찾아내고 검증 (v3.0 Reference)"""
    
    def __init__(self, client: GeminiClient):
        self.client = client
        self.splitter = Splitter()
        self.sampler = Sampler()
    
    def find_best_pattern(
        self,
        target_file: str,
        initial_samples: str,
        filename: Optional[str] = None,
        encoding: str = 'utf-8'
    ) -> Tuple[Optional[str], Optional[str]]:
        """최적의 패턴 탐색 (v3.0 Plan C 정밀 추적 포함)"""
        
        # 1. 기대 화수 추출
        expected_count = 0
        if filename:
            nums = re.findall(r'\d+', filename)
            if nums: expected_count = int(nums[-1])

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
    
    def _analyze_pattern_v3(self, sample_text: str) -> Optional[str]:
        """NovelAIze-SSR v3.0 원본 프롬프트 복원"""
        prompt = f"""=== pattern_analysis ===
You are an expert in Regex (Regular Expressions) and Text Analysis.
Analyze the following Novel Text Samples and identify the Pattern used for Chapter Titles.

[Tasks]
1. Find the most consistent pattern that denotes a new chapter start.
   Examples: "제 1 화", "Chapter 1", "1화.", "Ep.1"
2. Create a Python Compatible Regular Expression (Regex) to match these chapter titles.
   - Use `\s*` for flexible whitespace.
   - Use `\d+` for numbers.
3. OUTPUT ONLY the raw Regex string. No markdown, no content.
   - If no pattern found, return "NO_PATTERN_FOUND".

[Novel Text Samples]
{sample_text[:30000]}
"""
        try:
            response = self.client.generate_content(prompt)
            # 마크다운 및 불필요 텍스트 정제
            result = response.strip().replace("```python", "").replace("```re", "").replace("```", "").replace("r'", "").replace("'", "").strip()
            if "NO_PATTERN_FOUND" in result: return None
            # 줄바꿈이 있는 경우 첫 줄만 사용
            result = result.splitlines()[0] if result else None
            
            # [M-Hotfix] 정규식 유효성 사전 검증
            if result:
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
        """100% 일치를 위한 최종 보정 (v3.0 확장)"""
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
        
        # 부족 시: 갭 분석 정밀화
        if actual_count < expected_count:
            logger.info(f"   🔄 부족 화수 추적 중 (누락: {expected_count - actual_count}개)")
            gaps = self.splitter.find_large_gaps(target_file, matches)
            pattern = current_pattern
            for gap in gaps:
                sample = self.sampler.extract_samples_from(target_file, gap['start'], length=30000, encoding=encoding)
                if not sample: continue
                new_p = self._analyze_pattern_v3(sample)
                if new_p:
                    test_p = f"{pattern}|{new_p}"
                    test_s = self.splitter.verify_pattern(target_file, test_p, encoding=encoding)
                    if test_s['match_count'] <= expected_count:
                        pattern = test_p
                        if test_s['match_count'] == expected_count: break
            return pattern

        return current_pattern

    def _try_fallback(self, target_file: str, encoding: str = 'utf-8') -> Tuple[Optional[str], Optional[str]]:
        for ptn in [r"\d+\s*화", r"제\s*\d+\s*화", r"\[\d+\]"]:
            stats = self.splitter.verify_pattern(target_file, ptn, encoding=encoding)
            if stats['match_count'] > 0: return (ptn, None)
        return (None, None)
