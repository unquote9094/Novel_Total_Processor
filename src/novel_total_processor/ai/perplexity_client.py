"""Perplexity API 클라이언트

웹 검색 (Search API), 표지 URL 추출 (Agent API), 표지 다운로드
"""

import os
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from PIL import Image
from io import BytesIO
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.config.loader import get_config

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """검색 결과"""
    title: str
    url: str
    snippet: str
    rating: Optional[float] = None
    cover_url: Optional[str] = None


class PerplexityClient:
    """Perplexity API 클라이언트"""
    
    def __init__(self):
        """초기화"""
        self.config = get_config()
        
        # API 키 확인
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not set - Perplexity features disabled")
            self.enabled = False
            return
        
        self.enabled = True
        
        # API 엔드포인트
        self.search_url = "https://api.perplexity.ai/search"
        self.agent_url = "https://api.perplexity.ai/v1/responses"
        
        # Rate limiting
        self.rate_limit = self.config.api.perplexity.rate_limit
        self.last_call_time = 0
        self.min_interval = 60.0 / self.rate_limit
        
        # 표지 저장 디렉토리
        self.cover_dir = Path(self.config.paths.covers)
        self.cover_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"PerplexityClient initialized: rate_limit={self.rate_limit} RPM")
    
    def _wait_for_rate_limit(self) -> None:
        """Rate limit 대기"""
        if not self.enabled:
            return
        
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_interval:
            wait_time = self.min_interval - elapsed
            logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        self.last_call_time = time.time()
    
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """웹 검색 (Search API)
        
        Args:
            query: 검색 쿼리
            max_results: 최대 결과 수
        
        Returns:
            SearchResult 리스트
        """
        if not self.enabled:
            logger.warning("Perplexity disabled - returning empty results")
            return []
        
        self._wait_for_rate_limit()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "max_results": max_results,
            "search_language_filter": ["ko"],  # 한국어 우선
        }
        
        try:
            logger.debug(f"Searching: {query}")
            response = requests.post(
                self.search_url,
                headers=headers,
                json=payload,
                timeout=self.config.api.perplexity.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                ))
            
            logger.debug(f"Found {len(results)} results")
            return results
        
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def search_novel_info(self, title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """소설 정보 검색
        
        Args:
            title: 소설 제목
            author: 작가명 (선택)
        
        Returns:
            {"rating": float, "cover_url": str, "tags": [str]} 또는 None
        """
        if not self.enabled:
            return None
        
        # 검색 쿼리 생성
        query = f"{title} 소설"
        if author:
            query += f" {author}"
        query += " 별점 표지 리디북스 교보문고"
        
        results = self.search(query, max_results=3)
        
        if not results:
            return None
        
        # 첫 번째 결과에서 정보 추출 시도
        # (실제로는 Agent API로 상세 페이지 파싱 필요)
        # 여기서는 간단히 URL만 반환
        return {
            "rating": None,  # 실제 구현 시 Agent API로 추출
            "cover_url": None,  # 실제 구현 시 Agent API로 추출
            "tags": [],
            "source_url": results[0].url if results else None
        }
    
    def download_cover(self, cover_url: str, novel_id: int) -> Optional[str]:
        """표지 이미지 다운로드
        
        Args:
            cover_url: 표지 이미지 URL
            novel_id: 소설 ID
        
        Returns:
            저장된 파일 경로 또는 None
        """
        if not cover_url:
            return None
        
        try:
            logger.debug(f"Downloading cover: {cover_url}")
            
            # 이미지 다운로드
            response = requests.get(cover_url, timeout=10)
            response.raise_for_status()
            
            # PIL로 열기
            img = Image.open(BytesIO(response.content))
            
            # 리사이즈 (600x900)
            target_size = (
                self.config.epub.cover_size["width"],
                self.config.epub.cover_size["height"]
            )
            img.thumbnail(target_size, Image.Resampling.LANCZOS)
            
            # 저장
            cover_path = self.cover_dir / f"{novel_id}.jpg"
            img.convert("RGB").save(cover_path, "JPEG", quality=90)
            
            logger.info(f"✅ Cover saved: {cover_path}")
            return str(cover_path)
        
        except Exception as e:
            logger.error(f"Cover download failed: {e}")
            return None
    
    def batch_search(self, queries: List[str]) -> List[List[SearchResult]]:
        """배치 검색 (멀티쿼리)
        
        Args:
            queries: 검색 쿼리 리스트 (최대 5개)
        
        Returns:
            각 쿼리별 SearchResult 리스트
        """
        if not self.enabled:
            return [[] for _ in queries]
        
        if len(queries) > 5:
            logger.warning(f"Too many queries ({len(queries)}), splitting into batches")
        
        results = []
        for i in range(0, len(queries), 5):
            batch = queries[i:i+5]
            logger.info(f"Batch search: {len(batch)} queries")
            
            for query in batch:
                results.append(self.search(query))
        
        return results
