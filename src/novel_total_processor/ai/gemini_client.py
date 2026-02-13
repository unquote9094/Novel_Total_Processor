"""Gemini API 클라이언트 (google-genai SDK)

메타데이터 추출, Rate limiting, 응답 캐싱
"""

import os
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
    
    def _get_cache_path(self, file_hash: str) -> Path:
        """캐시 파일 경로 반환"""
        return self.cache_dir / f"{file_hash}.json"
    
    def _load_from_cache(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """캐시에서 로드"""
        cache_path = self._get_cache_path(file_hash)
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.debug(f"Cache hit: {file_hash[:8]}...")
                return data
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")
        return None
    
    def _save_to_cache(self, file_hash: str, data: Dict[str, Any]) -> None:
        """캐시에 저장"""
        cache_path = self._get_cache_path(file_hash)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Cache saved: {file_hash[:8]}...")
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

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
                    temperature=0.1,
                    max_output_tokens=2048, # 응답 끊김 방지 (2048로 확장)
                    # Google Search Grounding 활성화 (진짜 웹 검색)
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    response_mime_type="application/json" # JSON 응답 강제
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
    
    def generate_content(self, prompt: str) -> str:
        """Gemini API 호출 (일반 용도)"""
        return self._call_api(prompt)
    
    def extract_metadata_from_filename(self, filename: str, file_hash: str) -> NovelMetadata:
        """파일명에서 메타데이터 추출"""
        # 프롬프트 생성
        prompt = self._build_metadata_prompt(filename)
        
        # API 호출
        logger.info(f"🔍 Gemini Analysis: {filename}")
        response_text = self._call_api(prompt)
        
        # 응답 파싱
        metadata = self._parse_metadata_response(response_text, filename)
        
        # 캐시 저장
        self._save_to_cache(file_hash, metadata.__dict__)
        
        return metadata
    
    def _build_metadata_prompt(self, filename: str) -> str:
        """메타데이터 추출 프롬프트 생성"""
        return f"""다음 소설 파일명에서 메타데이터를 추출하세요.

파일명: {filename}

다음 형식의 JSON으로 응답하세요:
{{
  "title": "소설 제목",
  "author": "작가명 (없으면 null)",
  "genre": "장르 (판타지/로맨스/무협 등, 없으면 null)",
  "tags": ["태그1", "태그2"],
  "status": "완결/연재/휴재",
  "episode_range": "1~340화",
  "rating": 0.0,
  "cover_url": "공식 표지 이미지 URL (없으면 null)",
  "platform": "공식 연재 플랫폼 명칭",
  "last_updated": "최종 업데이트 날짜 YYYY-MM-DD",
  "official_url": "당신이 정보를 추출한 가장 정확한 공식 상세 페이지 URL"
}}

규칙:
1. **Google 검색 도구를 사용하여 공식 상세 페이지 URL(리디, 카카오, 네이버, 노벨피아, 문피아 등)을 최우선으로 찾으십시오.**
2. **찾은 공식 상세 페이지의 정보를 기반으로 정확한 데이터를 추출하십시오.**
3. **official_url 필드에는 당신이 실제 방문한 소설 상세 페이지 URL을 반드시 기입하십시오.**
4. **표지 이미지는 공식 일러스트 URL을 찾되, 사이트 로고(logo), 아이콘(icon), 혹은 기본 이미지(svg, default, ico)는 절대 기입하지 마십시오.**
5. **반드시 서론이나 설명 없이 { 로 시작하여 } 로 끝나는 순수 JSON 데이터만 출력하십시오. 응답이 잘리지 않도록 핵심 정보 위주로 간결하게 작성하십시오.**
6. **모든 정보는 반드시 한국어로 번역하십시오.** (장르, 태그, 상태 등)
"""
    
    def _parse_metadata_response(self, response_text: str, filename: str) -> NovelMetadata:
        """응답 파싱"""
        try:
            json_text = response_text.strip()
            if json_text.startswith("```"):
                parts = json_text.split("```")
                json_text = parts[1]
                if json_text.startswith("json"):
                    json_text = json_text[4:]
            
            data = json.loads(json_text.strip())
            
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
