"""Gemini API 클라이언트

메타데이터 추출, Rate limiting, 응답 캐싱
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import google.generativeai as genai
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


class GeminiClient:
    """Gemini API 클라이언트"""
    
    def __init__(self):
        """초기화"""
        self.config = get_config()
        self.model = None
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
                "GEMINI_API_KEY 환경변수가 설정되지 않았습니다.\n"
                "Environment variable GEMINI_API_KEY is not set.\n"
                "설정 방법 (How to set):\n"
                "  PowerShell: $env:GEMINI_API_KEY=\"your_api_key\"\n"
                "  CMD: set GEMINI_API_KEY=your_api_key\n"
                "  또는 .env 파일 사용 (or use .env file)"
            )
        
        # Gemini 설정
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.config.api.gemini.model)
        self._initialized = True
        
        logger.info(f"GeminiClient initialized: model={self.config.api.gemini.model}")
    
    def _wait_for_rate_limit(self) -> None:
        """Rate limit 대기"""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_interval:
            wait_time = self.min_interval - elapsed
            logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        self.last_call_time = time.time()
    
    def _get_cache_path(self, file_hash: str) -> Path:
        """캐시 파일 경로 반환
        
        Args:
            file_hash: 파일 해시
        
        Returns:
            캐시 파일 경로
        """
        return self.cache_dir / f"{file_hash}.json"
    
    def _load_from_cache(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """캐시에서 로드
        
        Args:
            file_hash: 파일 해시
        
        Returns:
            캐시된 응답 또는 None
        """
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
        """캐시에 저장
        
        Args:
            file_hash: 파일 해시
            data: 저장할 데이터
        """
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
        """Gemini API 호출 (재시도 포함)
        
        Args:
            prompt: 프롬프트
        
        Returns:
            응답 텍스트
        """
        self._ensure_initialized()  # API 사용 전 초기화
        self._wait_for_rate_limit()
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 2048,
                }
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
    
    def extract_metadata_from_filename(self, filename: str, file_hash: str) -> NovelMetadata:
        """파일명에서 메타데이터 추출
        
        Args:
            filename: 파일명
            file_hash: 파일 해시 (캐싱용)
        
        Returns:
            NovelMetadata 객체
        """
        # 캐시 확인
        cached = self._load_from_cache(file_hash)
        if cached:
            return NovelMetadata(**cached)
        
        # 프롬프트 생성
        prompt = self._build_metadata_prompt(filename)
        
        # API 호출
        logger.debug(f"Extracting metadata: {filename}")
        response_text = self._call_api(prompt)
        
        # 응답 파싱
        metadata = self._parse_metadata_response(response_text, filename)
        
        # 캐시 저장
        self._save_to_cache(file_hash, metadata.__dict__)
        
        return metadata
    
    def _build_metadata_prompt(self, filename: str) -> str:
        """메타데이터 추출 프롬프트 생성
        
        Args:
            filename: 파일명
        
        Returns:
            프롬프트 문자열
        """
        return f"""다음 소설 파일명에서 메타데이터를 추출하세요.

파일명: {filename}

다음 형식의 JSON으로 응답하세요:
{{
  "title": "소설 제목",
  "author": "작가명 (없으면 null)",
  "genre": "장르 (판타지/로맨스/무협 등, 없으면 null)",
  "tags": ["태그1", "태그2"] (없으면 빈 배열),
  "status": "완결/연재/휴재 (없으면 null)",
  "episode_range": "1~340화" 형식 (없으면 null),
  "rating": null (파일명에서는 알 수 없음)
}}

규칙:
1. 제목은 대괄호[], 소괄호() 등의 접두사/접미사를 제거하고 정규화
2. 작가명이 파일명에 있으면 추출
3. 장르는 대표 장르 1개만
4. 태그는 최대 5개까지
5. 화수는 "1~340화" 형식으로 정규화
6. JSON만 출력 (설명 없이)
"""
    
    def _parse_metadata_response(self, response_text: str, filename: str) -> NovelMetadata:
        """응답 파싱
        
        Args:
            response_text: API 응답
            filename: 원본 파일명 (fallback용)
        
        Returns:
            NovelMetadata 객체
        """
        try:
            # JSON 추출 (```json ... ``` 제거)
            json_text = response_text.strip()
            if json_text.startswith("```"):
                json_text = json_text.split("```")[1]
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
                rating=data.get("rating")
            )
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            logger.debug(f"Response: {response_text}")
            # Fallback: 파일명을 제목으로
            return NovelMetadata(title=filename)
    
    def extract_batch(self, files: List[Dict[str, str]], batch_size: int = 10) -> List[NovelMetadata]:
        """배치 메타데이터 추출
        
        Args:
            files: [{"filename": "...", "hash": "..."}, ...]
            batch_size: 배치 크기
        
        Returns:
            NovelMetadata 리스트
        """
        results: List[NovelMetadata] = []
        total = len(files)
        
        logger.info(f"Extracting metadata for {total} files (batch_size={batch_size})...")
        
        for i in range(0, total, batch_size):
            batch = files[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}")
            
            for file in batch:
                metadata = self.extract_metadata_from_filename(
                    file["filename"],
                    file["hash"]
                )
                results.append(metadata)
            
            logger.info(f"  Completed {min(i+batch_size, total)}/{total}")
        
        logger.info(f"✅ Batch extraction complete: {len(results)} files")
        return results
