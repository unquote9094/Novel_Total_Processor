from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions
import os
import asyncio
from typing import Optional

from novel_aize_ssr.base_client import BaseAIClient, RateLimitError, CensorshipError, AuthenticationError, AIError
from novel_aize_ssr.config import load_prompts, get_prompt

class GeminiClient(BaseAIClient):
    """
    구글 Gemini API 클라이언트. 
    BaseAIClient를 상속받아 표준 인터페이스와 고도화된 에러 핸들링을 제공합니다.
    """
    def __init__(self, api_key: Optional[str] = None, 
                 model_name: str = "gemini-3-flash-preview", 
                 genre: str = "general"):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            # 여기서는 Exception을 던지는 대신 로깅 후 나중에 analyze 호출 시 체크
            pass
            
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
        self.genre = genre

    def _map_exception(self, e: Exception) -> AIError:
        """Google SDK 예외를 커스텀 예외로 매핑"""
        if isinstance(e, google_exceptions.ResourceExhausted):
            return RateLimitError(f"Gemini Rate Limit: {e}")
        elif isinstance(e, google_exceptions.Unauthenticated):
            return AuthenticationError(f"Gemini Auth Fail: {e}")
        elif isinstance(e, google_exceptions.InvalidArgument):
            return AIError(f"Invalid Arguments: {e}")
        return AIError(f"Gemini Unknown Error: {e}")

    def analyze_pattern(self, text_samples: str) -> Optional[str]:
        if not self.api_key:
            raise AuthenticationError("GOOGLE_API_KEY is missing.")

        prompts = load_prompts()
        system_prompt = prompts.get("pattern_analysis", "")
        
        prompt = f"{system_prompt}\n\n[Novel Text Samples]\n{text_samples[:50000]}"

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            # [Validation] Finish Reason 체크 (검열 등)
            if response.candidates and response.candidates[0].finish_reason:
                fr = response.candidates[0].finish_reason
                if fr in [3, 5, "SAFETY", "FinishReason.SAFETY"]:
                    raise CensorshipError("Pattern analysis blocked by safety filters.")

            if not response.text:
                return None
                
            result = response.text.strip()
            # Clean Markdown
            result = result.replace("```python", "").replace("```re", "").replace("```", "").strip()
            return result

        except Exception as e:
            raise self._map_exception(e)

    async def summarize_async(self, text: str, context: Optional[str] = None) -> str:
        if not self.api_key:
            raise AuthenticationError("GOOGLE_API_KEY is missing.")
            
        genre_prompt = get_prompt(self.genre)
        
        # Context Chaining: 이전 맥락이 있으면 프롬프트에 주입
        context_str = f"\n[이전 줄거리 요약]\n{context}\n" if context else ""
        
        prompt = f"{genre_prompt}\n{context_str}\n[Text to Summarize]\n{text[:30000]}"
        
        try:
            loop = asyncio.get_running_loop()
            def sync_call():
                return self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
            
            response = await loop.run_in_executor(None, sync_call)
            
            if response is None or not hasattr(response, 'text') or response.text is None:
                # 검열 여부 재확인
                if response and hasattr(response, 'candidates') and response.candidates:
                    if response.candidates[0].finish_reason in [3, 5, "SAFETY"]:
                        return "[CENSORED_BLOCK]"
                return "Error: Empty or Blocked Response"
                
            return response.text.strip()
            
        except Exception as e:
            # 비동기 상황에서의 예외 매핑
            mapped = self._map_exception(e)
            if isinstance(mapped, RateLimitError):
                return "Error: 429 Rate Limit" # 매니저에서 캐치하도록 문자열 유지 혹은 raise
            raise mapped

