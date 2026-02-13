"""Gemini API 클라이언트 (google-genai SDK)

메타데이터 추출, Rate limiting, 응답 캐싱
"""

import os
import re
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.config.loader import get_config

logger = get_logger(__name__)


@dataclass
class NovelMetadata:
    """소설 메타데이터"""
    title: str
    author: Optional[str] = None
    genre: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    episode_range: Optional[str] = None
    rating: Optional[float] = None
    cover_url: Optional[str] = None
    platform: Optional[str] = None  # 연재 플랫폼 (노벨피아, 문피아 등)
    last_updated: Optional[str] = None  # 최종 업데이트 날짜 (YYYY-MM-DD)
    official_url: Optional[str] = None  # [M-49] 추가: AI가 참고한 공식 페이지 URL


class GeminiClient:
    """Gemini API 클라이언트 (google.genai)"""
    
    def __init__(self):
        """초기화"""
        self.config = get_config()
        self.client = None  # genai.Client
        self.model_name = self.config.api.gemini.model
        self._initialized = False
        
        # Rate limiting (RPM)
        self.rate_limit = self.config.api.gemini.rate_limit
        self.last_call_time = 0
        self.min_interval = 60.0 / self.rate_limit  # 초 단위
        
        # 캐시 디렉토리
        self.cache_dir = Path("data/cache/ai_meta")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"GeminiClient created (lazy init): rate_limit={self.rate_limit} RPM")
    
    def _ensure_initialized(self):
        """API 사용 전 초기화 확인"""
        if self._initialized:
            return
        
        # API 키 확인
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "❌ GEMINI_API_KEY 환경변수가 설정되지 않았습니다.\n"
                "참고: 구글 AI 스튜디오에서 API 키를 발급받으세요.\n"
                "\n"
                "설정 방법:\n"
                "  1. .env 파일 생성 후 'GEMINI_API_KEY=your_key' 입력\n"
                "  2. 또는 터미널에서 설정:\n"
                "     PowerShell: $env:GEMINI_API_KEY='your_key'\n"
                "     CMD: set GEMINI_API_KEY=your_key"
            )
        
        # google.genai Client 초기화
        try:
            self.client = genai.Client(api_key=api_key)
            self._initialized = True
            logger.info(f"GeminiClient initialized: model={self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Client: {e}")
            raise

    def _wait_for_rate_limit(self) -> None:
        """Rate limit 대기"""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_interval:
            wait_time = self.min_interval - elapsed
            logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        self.last_call_time = time.time()
    
    # 캐시 기능 영구 삭제 (사용자 요청)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception)
    )
    def _call_api(self, prompt: str) -> str:
        """Gemini API 호출 (재시도 포함)"""
        self._ensure_initialized()
        self._wait_for_rate_limit()
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0, # 결정론적 응답을 위해 0으로 고정
                    max_output_tokens=2048,
                    # Google Search Grounding 활성화
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    # response_mime_type="application/json"  # [Hotfix v3] Grounding과의 충돌 방지를 위해 주석 처리
                )
            )
            
            # [Hotfix v4] Grounding Metadata 로깅 (사용자 가시성 확보)
            if response.candidates and response.candidates[0].grounding_metadata:
                gm = response.candidates[0].grounding_metadata
                if gm.search_entry_point:
                    # 실제 수행된 검색 쿼리 힌트 추출
                    logger.info(f"   🔍 [Gemini Grounding] 검색 기능을 활용하여 정보를 수집 중입니다.")
                
                # 방문한 출처(Citations) 출력
                if gm.grounding_chunks:
                    sources = []
                    for chunk in gm.grounding_chunks:
                        if chunk.web and chunk.web.uri:
                            sources.append(chunk.web.uri)
                    
                    if sources:
                        unique_sources = list(set(sources))[:3] # 상위 3개만 출력
                        logger.info(f"   🌐 [Sources] {', '.join(unique_sources)}")
            
            return response.text
        except Exception as e:
            # [Hotfix v5] 503 Server Overloaded 감지 시 즉시 포기 (Circuit Breaker)
            error_str = str(e)
            if "503" in error_str or "Overloaded" in error_str or "High demand" in error_str:
                logger.warning(f"   ⚠️ Gemini Server 503/Overloaded. Skipping retries to save time. (Switching to Perplexity)")
                return None  # 재시도 루프 탈출 및 즉시 실패 처리
            
            logger.error(f"Gemini API error: {e}")
            raise e
    
    def generate_content(self, prompt: str) -> Optional[str]: # Return type changed to Optional[str]
        """Gemini API 호출 (일반 용도)"""
        return self._call_api(prompt)
    
    def extract_metadata_from_filename(self, filename: str, file_hash: str) -> Optional[NovelMetadata]: # Return type changed
        """파일명에서 메타데이터 추출"""
        # 프롬프트 생성
        prompt = self._build_metadata_prompt(filename)
        
        # API 호출
        logger.info(f"🔍 Gemini Analysis: {filename}")
        response_text = self._call_api(prompt)
        
        if not response_text:
            logger.warning(f"   ⚠️ Gemini returned no response (or skipped due to 503).")
            return None
            
        # 응답 파싱
        metadata = self._parse_metadata_response(response_text, filename)
        
        # 캐시 저장
        self._save_to_cache(file_hash, metadata.__dict__)
        
        return metadata
    
    def _build_metadata_prompt(self, filename: str) -> str:
        """메타데이터 추출 프롬프트 생성 (Deep Search 강화)"""
        return f"""당신은 소설 메타데이터 전문가입니다. 다음 파일명에서 소설의 정보를 구글 검색을 통해 상세히 찾아내십시오.

파일명: {filename}

[수행 과제]
1. **Google 검색 도구를 반드시 사용**하여 이 소설의 최신 공식 상세 페이지(리디, 카카오, 네이버, 노벨피아, 문피아, 조아라 등)를 찾으십시오.
2. 공식 페이지에 적힌 **가장 정확하고 풍부한 정보**를 긁어오십시오.
3. 특히 **장르, 작가, 평점, 그리고 가능한 한 많은 상세 태그(최소 5개 이상)**를 찾아내십시오.
4. 공식 일러스트(표지) URL이 있다면 반드시 포함하십시오. (로고/아이콘 제외)

[응답 형식: JSON ONLY]
{{
  "title": "소설 제목",
  "author": "작가명",
  "genre": "장르 (예: 현대 판타지, 로맨스 판타지 등)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "status": "완결/연재/휴재",
  "episode_range": "총 화수 혹은 출판 권수",
  "rating": 0.0,
  "platform": "최우선 연재 플랫폼 명칭",
  "last_updated": "최종 업데이트 날짜 YYYY-MM-DD",
  "official_url": "실제 방문한 공식 상세 페이지 주소",
  "cover_url": "공식 표지 이미지 직접 링크"
}}

[주의사항]
- 모든 텍스트는 **한국어**로 출력하십시오.
- JSON 블록만 출력하십시오. (마크다운 포함)
"""
    
    def _parse_metadata_response(self, response_text: str, filename: str) -> NovelMetadata:
        """응답 파싱"""
        try:
            # [Hotfix v5] JSON 파싱 로직 강화 (최외곽 중괄호 우선 탐색)
            # 마크다운 코드 블록 유무와 상관없이 가장 바깥쪽의 { ... } 구조를 찾음
            # re.DOTALL로 개행 문자 포함 매칭
            main_json_match = re.search(r'(\{[\s\S]*\})', response_text)
            
            if main_json_match:
                json_text = main_json_match.group(1)
            else:
                # 매칭되지 않으면 원본 사용 (혹시 모를 경우 대비)
                json_text = response_text.strip()
            
            # 끊긴 JSON 자동 복구 (Hotfix v3 유지)
            
            # 3. 끊긴 JSON 복구 시도 (장애 방어)
            if json_text.count('{') > json_text.count('}'):
                # 닫는 중괄호가 부족하면 강제로 닫아줌 (끊김 발생 시 최소한의 파싱 보장)
                json_text += '}' * (json_text.count('{') - json_text.count('}'))
            
            data = json.loads(json_text)
            
            return NovelMetadata(
                title=data.get("title", filename),
                author=data.get("author"),
                genre=data.get("genre"),
                tags=data.get("tags", []),
                status=data.get("status"),
                episode_range=data.get("episode_range"),
                rating=data.get("rating"),
                cover_url=self._filter_cover_url(data.get("cover_url")),
                platform=data.get("platform"),
                last_updated=data.get("last_updated"),
                official_url=data.get("official_url")
            )
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            logger.debug(f"Response: {response_text}")
            return NovelMetadata(title=filename)

    def _filter_cover_url(self, url: Optional[str]) -> Optional[str]:
        """부적절한 이미지 URL 필터링 (Hotfix)"""
        if not url: return None
        bad_patterns = [".svg", ".ico", "logo", "icon", "default", "mark"]
        url_lower = url.lower()
        if any(p in url_lower for p in bad_patterns):
            logger.warning(f"   ⚠️  부적절한 이미지 URL 감별되어 스킵: {url}")
            return None
        return url
    
    def extract_batch(self, files: List[Dict[str, str]], batch_size: int = 10) -> List[NovelMetadata]:
        """배치 메타데이터 추출"""
        results: List[NovelMetadata] = []
        for file in files:
            metadata = self.extract_metadata_from_filename(file["filename"], file["hash"])
            results.append(metadata)
        return results
