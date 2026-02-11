from abc import ABC, abstractmethod
from typing import Optional, List

class BaseAIClient(ABC):
    """
    다양한 AI 공급자(Gemini, Claude, GPT 등)를 지원하기 위한 추상 인터페이스.
    """
    
    @abstractmethod
    def analyze_pattern(self, text_samples: str) -> Optional[str]:
        """소설 텍스트 샘플에서 챕터 패턴(Regex) 추출"""
        pass
        
    @abstractmethod
    async def summarize_async(self, text: str, context: Optional[str] = None) -> str:
        """비동기 텍스트 요약. 이전 화 맥락(context) 지원."""
        pass

class AIError(Exception):
    """AI API 관련 기본 예외 클래스"""
    pass

class RateLimitError(AIError):
    """429 Resource exhausted / Rate limit exceeded"""
    pass

class CensorshipError(AIError):
    """FinishReason.SAFETY 등 정책 위반으로 인한 차단"""
    pass

class AuthenticationError(AIError):
    """API Key 오류 등 인증 실패"""
    pass
