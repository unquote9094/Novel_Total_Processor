from typing import Optional
from novel_aize_ssr.sampler import Sampler
from novel_aize_ssr.splitter import Splitter
from novel_aize_ssr.base_client import BaseAIClient, RateLimitError, CensorshipError, AIError

class PatternManager:
    """
    AI를 사용하여 소설의 최적 챕터 분할 패턴을 찾아내고 검증하는 클래스.
    Adaptive Retry (Plan C) 및 범용 패턴 시도(Plan B) 로직을 포함합니다.
    """
    def __init__(self, client: BaseAIClient, printer=None):
        self.client = client
        self.splitter = Splitter()
        self.sampler = Sampler()
        self.printer = printer or print

    def log(self, msg: str):
        self.printer(msg)

    def find_best_pattern(self, target_file: str, initial_samples: str) -> Optional[str]:
        self.log(f"   -> 챕터 제목 패턴을 찾고 있습니다...")
        
        try:
            pattern = self.client.analyze_pattern(initial_samples)
            if not pattern:
                return self._try_fallback(target_file)
        except CensorshipError:
            self.log("   🚫 [Censored] 패턴 분석이 안전 필터에 의해 차단되었습니다.")
            return self._try_fallback(target_file)
        except AIError as e:
            self.log(f"   ❌ [AI Error] 패턴 분석 실패: {e}")
            return self._try_fallback(target_file)

        self.log(f"   [AI 분석 결과] 발견된 패턴: {pattern}")
        
        verify_stats = self.splitter.verify_pattern(target_file, pattern)
        if verify_stats['coverage_ok']:
            return pattern
            
        self.log(f"   ⚠️  [Warning] 패턴 커버리지 낮음 ({verify_stats['last_match_ratio']*100:.1f}%)")
        return self._run_adaptive_retry(target_file, pattern, verify_stats)

    def _run_adaptive_retry(self, target_file: str, current_pattern: str, verify_stats: dict) -> str:
        retry_count = 0
        # 99% 목표를 위해 재시도 횟수를 5회에서 10회로 대폭 상향
        max_retries = 10 
        pattern = current_pattern
        stats = verify_stats
        
        self.log(f"   -> [Plan C] 99% 달성을 위한 정밀 추적 시작 (최대 {max_retries}단계)")

        while not stats['coverage_ok'] and retry_count < max_retries:
            retry_count += 1
            self.log(f"   🔄 [Retry {retry_count}/{max_retries}] 누락된 화차 위치({stats['last_match_pos']})에서 다음 패턴 분석 중...")
            
            fail_pos = stats['last_match_pos']
            retry_sample = self.sampler.extract_samples_from(target_file, fail_pos)
            
            if not retry_sample: break
                
            try:
                new_pattern = self.client.analyze_pattern(retry_sample)
                if new_pattern:
                    combined_pattern = f"{pattern}|{new_pattern}"
                    verify_stats_new = self.splitter.verify_pattern(target_file, combined_pattern)
                    
                    # 조금이라도 나아지면 적용
                    if verify_stats_new['last_match_ratio'] > stats['last_match_ratio'] or verify_stats_new['tail_size'] < stats['tail_size']:
                        pattern = combined_pattern
                        stats = verify_stats_new
                        if stats['coverage_ok']: 
                            self.log(f"   ✨ [Success] 목표 커버리지(99%) 달성!")
                            break
                    else:
                        self.log("   ❌ 패턴 추가 시도했으나 개선되지 않음. 다음 단계 진행...")
            except AIError:
                break
                
        return pattern

    def _try_fallback(self, target_file: str, current_best: Optional[str] = None) -> Optional[str]:
        self.log("   -> [Plan B] 범용 패턴 시도...")
        fallback_pattern = r"\d+\s*화"
        verify_stats_fallback = self.splitter.verify_pattern(target_file, fallback_pattern)
        
        if verify_stats_fallback['last_match_ratio'] > 0.9:
            return fallback_pattern
        return current_best

