import asyncio
import time
from typing import Optional

class RateLimiter:
    """
    Token Bucket 알고리즘을 사용한 정밀한 속도 제한 클래스.
    지정된 RPM(분당 요청 수)을 초과하지 않도록 제어합니다.
    """
    def __init__(self, rpm: int = 15):
        """
        :param rpm: 분당 최대 요청 수 (Requests Per Minute)
        """
        self.rpm = rpm
        self.interval = 60.0 / rpm  # 요청 간 최소 간격 (초)
        self.last_call_time = 0.0
        self.lock = asyncio.Lock()
        self.has_logged = False
        
    async def acquire(self):
        """
        토큰을 획득할 때까지 대기합니다.
        여러 태스크가 동시에 호출해도 순차적으로 처리됩니다.
        """
        async with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_call_time
            
            if elapsed < self.interval:
                wait_time = self.interval - elapsed
                if not self.has_logged:
                    print(f"[RateLimiter] RPM={self.rpm} (Interval={self.interval:.2f}s) -> Waiting {wait_time:.2f}s... (First Log Only)")
                    self.has_logged = True
                await asyncio.sleep(wait_time)
            
            self.last_call_time = time.time()

    def update_rpm(self, new_rpm: int):
        """
        실행 중 RPM을 동적으로 변경합니다.
        """
        self.rpm = new_rpm
        self.interval = 60.0 / new_rpm
