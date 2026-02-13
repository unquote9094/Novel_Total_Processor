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
        """웹 검색 (Search API)"""
        if not self.enabled:
            return []
        
        self._wait_for_rate_limit()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "max_results": max_results,
            "search_language_filter": ["ko"],
        }
        
        try:
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
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def search_novel_info(self, title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """소설 정보 상세 검색 (Chat API + Online Model)"""
        if not self.enabled:
            return None
        
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        system_prompt = "You are a helpful assistant. Search for the novel info. Output valid JSON only."
        user_prompt = f"""
Search for the Korean web novel "{title}"{f' by {author}' if author else ''}.
1. First, find its OFFICIAL and LATEST detail page URL from platforms like Ridi, KakaoPage, Naver Series, Novelpia, Munpia, Joara.
2. Extract info from that official page.
3. Find its official title, author, rating (out of 10.0), genre, tags, status, episode range, last updated date, and cover image URL.

Response Format (JSON):
{{
    "title": "string",
    "author": "string",
    "rating": 0.0,
    "genre": "string",
    "tags": ["tag1", "tag2"],
    "status": "string",
    "episode_range": "string",
    "source_url": "당신이 실제 정보를 가져온 공식 상세 페이지 URL",
    "cover_url": "실제 도서 표지 이미지 URL (로고 제외)",
    "platform": "Platform Name",
    "last_updated": "YYYY-MM-DD"
}}

RULES:
1. **ALWAYS translate genre, tags, and status into Korean.**
2. **DO NOT provide site logos (e.g., logo.svg, icon) or default images as a cover_url.** Only actual book covers.
3. **source_url MUST be the official detail page URL.**
"""
        
        payload = {
            "model": self.config.api.perplexity.agent_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1
        }
        
        try:
            logger.info(f"   🤖 Asking Perplexity (Online): {title}")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # JSON 파싱
            import re
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            
            data = json.loads(json_str)
            
            # 상세 로깅
            logger.info(f"     [Perplexity Result]")
            logger.info(f"       - Title: {data.get('title')}")
            logger.info(f"       - Author: {data.get('author')}")
            logger.info(f"       - Genre: {data.get('genre')}")
            logger.info(f"       - Rating: {data.get('rating')}")
            logger.info(f"       - Tags: {', '.join(data.get('tags', [])) if data.get('tags') else '[]'}")
            logger.info(f"       - Status: {data.get('status')}")
            logger.info(f"       - Episodes: {data.get('episode_range')}")
            logger.info(f"       - Platform: {data.get('platform')}")
            logger.info(f"       - Updated: {data.get('last_updated')}")
            logger.info(f"       - Source: {data.get('source_url')}")
            
            return data
        except Exception as e:
            logger.error(f"Perplexity Deep Search failed: {e}")
            return None

    def download_cover(self, cover_url: str, novel_id: int) -> Optional[str]:
        """표지 이미지 다운로드 (Hotfix: SVG/ICO 필터링 포함)"""
        if not cover_url:
            return None
        
        # [Hotfix] 이미지 형식 필터링 (SVG, ICO, Logo 배제)
        url_lower = cover_url.lower()
        bad_patterns = [".svg", ".ico", "logo", "icon", "default", "mark"]
        if any(p in url_lower for p in bad_patterns):
            logger.warning(f"   ⚠️  부적절한 이미지 형식 감별되어 다운로드 스킵: {cover_url}")
            return None

        try:
            logger.debug(f"Downloading cover: {cover_url}")
            response = requests.get(cover_url, timeout=10)
            response.raise_for_status()
            
            img = Image.open(BytesIO(response.content))
            target_size = (
                self.config.epub.cover_size["width"],
                self.config.epub.cover_size["height"]
            )
            img.thumbnail(target_size, Image.Resampling.LANCZOS)
            
            cover_path = self.cover_dir / f"{novel_id}.jpg"
            img.convert("RGB").save(cover_path, "JPEG", quality=90)
            
            logger.info(f"✅ Cover saved: {cover_path}")
            return str(cover_path)
        except Exception as e:
            logger.error(f"Cover download failed: {e}")
            return None
