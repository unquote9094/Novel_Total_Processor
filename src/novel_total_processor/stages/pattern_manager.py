"""패턴 관리자

AI를 사용하여 소설의 최적 챕터 분할 패턴을 찾아내고 검증
NovelAIze-SSR v3.0의 PatternManager 포팅 + 소제목 패턴 추가
"""

from typing import Optional, Tuple
from novel_total_processor.stages.sampler import Sampler
from novel_total_processor.stages.splitter import Splitter
from novel_total_processor.ai.gemini_client import GeminiClient
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


class PatternManager:
    """AI를 사용하여 소설의 최적 챕터 분할 패턴을 찾아내고 검증하는 클래스
    
    Adaptive Retry (Plan C) 및 범용 패턴 시도(Plan B) 로직을 포함
    """
    
    def __init__(self, client: GeminiClient):
        """
        Args:
            client: GeminiClient 인스턴스
        """
        self.client = client
        self.splitter = Splitter()
        self.sampler = Sampler()
    
    def find_best_pattern(
        self,
        target_file: str,
        initial_samples: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """최적의 챕터 패턴과 소제목 패턴을 찾기
        
        Args:
            target_file: 대상 파일 경로
            initial_samples: 초기 샘플 텍스트
        
        Returns:
            (chapter_pattern, subtitle_pattern) 튜플
        """
        logger.info("   -> 챕터 제목 패턴을 찾고 있습니다...")
        
        try:
            # AI에 2가지 요청: 챕터 패턴 + 소제목 패턴
            patterns = self._analyze_patterns(initial_samples)
            
            if not patterns or not patterns.get("chapter_pattern"):
                return self._try_fallback(target_file)
        
        except Exception as e:
            logger.error(f"   ❌ [AI Error] 패턴 분석 실패: {e}")
            return self._try_fallback(target_file)
        
        chapter_pattern = patterns["chapter_pattern"]
        subtitle_pattern = patterns.get("subtitle_pattern")
        
        logger.info(f"   [AI 분석 결과] 챕터 패턴: {chapter_pattern}")
        if subtitle_pattern:
            logger.info(f"   [AI 분석 결과] 소제목 패턴: {subtitle_pattern}")
        
        # 챕터 패턴 검증
        verify_stats = self.splitter.verify_pattern(target_file, chapter_pattern)
        
        if verify_stats['coverage_ok']:
            return (chapter_pattern, subtitle_pattern)
        
        logger.warning(
            f"   ⚠️  [Warning] 패턴 커버리지 낮음 ({verify_stats['last_match_ratio']*100:.1f}%)"
        )
        
        # Adaptive Retry
        final_pattern = self._run_adaptive_retry(target_file, chapter_pattern, verify_stats)
        return (final_pattern, subtitle_pattern)
    
    def _analyze_patterns(self, sample_text: str) -> dict:
        """AI에 샘플을 보내서 챕터 패턴 + 소제목 패턴 분석
        
        Args:
            sample_text: 샘플 텍스트
        
        Returns:
            {"chapter_pattern": str, "subtitle_pattern": str}
        """
        prompt = f"""다음은 소설 파일의 샘플입니다. 이 소설의 챕터 구분 패턴과 소제목 패턴을 분석해주세요.

샘플:
```
{sample_text[:10000]}  # 너무 길면 잘라서 전송
```

요청 1: 챕터 구분 정규식 패턴
- 각 화(에피소드)를 구분하는 패턴을 정규식으로 작성해주세요
- 예: r"━+\\s*.*?\\s*\\d+화\\s*━+" 또는 r"제\\s*\\d+\\s*화"

요청 2: 챕터 소제목/부제목 패턴
- 챕터 제목 다음에 나오는 소제목이나 부제목 패턴을 정규식으로 작성해주세요
- 예: r"^\\d+\\.\\s*.+$" (숫자. 제목 형식)
- 소제목이 없으면 null로 응답

응답 형식 (JSON):
{{
  "chapter_pattern": "정규식",
  "subtitle_pattern": "정규식 또는 null"
}}
"""
        
        try:
            response = self.client.generate_content(prompt)
            
            # JSON 파싱
            import json
            import re
            
            # JSON 블록 추출
            json_match = re.search(r'\{[^{}]*"chapter_pattern"[^{}]*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return result
            
            # JSON 없으면 텍스트에서 패턴 추출 시도
            chapter_match = re.search(r'chapter_pattern["\s:]+(["\'])(.*?)\1', response)
            if chapter_match:
                chapter_pattern = chapter_match.group(2)
                
                subtitle_match = re.search(r'subtitle_pattern["\s:]+(["\'])(.*?)\1', response)
                subtitle_pattern = subtitle_match.group(2) if subtitle_match else None
                
                return {
                    "chapter_pattern": chapter_pattern,
                    "subtitle_pattern": subtitle_pattern
                }
            
            logger.error(f"AI 응답에서 패턴을 추출할 수 없습니다: {response[:200]}")
            return {}
        
        except Exception as e:
            logger.error(f"패턴 분석 중 오류: {e}")
            return {}
    
    def _run_adaptive_retry(
        self,
        target_file: str,
        current_pattern: str,
        verify_stats: dict
    ) -> str:
        """Adaptive Retry: 99% 달성을 위한 정밀 추적
        
        Args:
            target_file: 대상 파일
            current_pattern: 현재 패턴
            verify_stats: 검증 통계
        
        Returns:
            최종 패턴
        """
        retry_count = 0
        max_retries = 10
        pattern = current_pattern
        stats = verify_stats
        
        logger.info(f"   -> [Plan C] 99% 달성을 위한 정밀 추적 시작 (최대 {max_retries}단계)")
        
        while not stats['coverage_ok'] and retry_count < max_retries:
            retry_count += 1
            logger.info(
                f"   🔄 [Retry {retry_count}/{max_retries}] "
                f"누락된 화차 위치({stats['last_match_pos']})에서 다음 패턴 분석 중..."
            )
            
            fail_pos = stats['last_match_pos']
            retry_sample = self.sampler.extract_samples_from(target_file, fail_pos)
            
            if not retry_sample:
                break
            
            try:
                new_patterns = self._analyze_patterns(retry_sample)
                new_pattern = new_patterns.get("chapter_pattern")
                
                if new_pattern:
                    combined_pattern = f"{pattern}|{new_pattern}"
                    verify_stats_new = self.splitter.verify_pattern(target_file, combined_pattern)
                    
                    # 조금이라도 나아지면 적용
                    if (verify_stats_new['last_match_ratio'] > stats['last_match_ratio'] or
                        verify_stats_new['tail_size'] < stats['tail_size']):
                        pattern = combined_pattern
                        stats = verify_stats_new
                        
                        if stats['coverage_ok']:
                            logger.info("   ✨ [Success] 목표 커버리지(99%) 달성!")
                            break
                    else:
                        logger.info("   ❌ 패턴 추가 시도했으나 개선되지 않음. 다음 단계 진행...")
            
            except Exception as e:
                logger.error(f"Retry 중 오류: {e}")
                break
        
        return pattern
    
    def _try_fallback(
        self,
        target_file: str,
        current_best: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """Plan B: 범용 패턴 시도
        
        Args:
            target_file: 대상 파일
            current_best: 현재 최선의 패턴
        
        Returns:
            (chapter_pattern, subtitle_pattern) 튜플
        """
        logger.info("   -> [Plan B] 범용 패턴 시도...")
        
        fallback_pattern = r"\d+\s*화"
        verify_stats_fallback = self.splitter.verify_pattern(target_file, fallback_pattern)
        
        if verify_stats_fallback['last_match_ratio'] > 0.9:
            return (fallback_pattern, None)
        
        return (current_best, None) if current_best else (None, None)
