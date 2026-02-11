import asyncio
from typing import List, Dict, Optional
from tqdm.asyncio import tqdm
from novel_aize_ssr.structure import Chapter
from novel_aize_ssr.gemini_client import GeminiClient
from novel_aize_ssr.checkpoint import CheckpointManager
from novel_aize_ssr.report_formatter import ReportFormatter
from novel_aize_ssr.rate_limiter import RateLimiter
from novel_aize_ssr.base_client import RateLimitError, CensorshipError, AIError

class SummarizeManager:
    """
    비동기 챕터 요약을 전담하는 매니저 클래스.
    컨텍스트 체이닝(이전 화 요약 고려) 및 지능형 속도 제어를 수행합니다.
    """
    def __init__(self, api_key: str, concurrency: int = 5, 
                 model_name: str = "gemini-3-flash-preview", 
                 genre: str = "general", 
                 checkpoint_manager: Optional[CheckpointManager] = None,
                 output_format: str = "plain", 
                 rate_limit_rpm: int = 15):
        self.client = GeminiClient(api_key=api_key, model_name=model_name, genre=genre)
        self.semaphore = asyncio.Semaphore(concurrency)
        self.rate_limiter = RateLimiter(rpm=rate_limit_rpm)
        self.checkpoint_manager = checkpoint_manager
        self.formatter = ReportFormatter(output_format=output_format)
        
        self.results: Dict[int, str] = {}
        self.completed_cids: List[int] = []
        self.all_chapters: List[Chapter] = []
        
        # [New] Context Chaining: 이전 화의 요약본을 저장 (cid 순서대로 처리 필요)
        self.context_cache: Dict[int, str] = {}

    async def summarize_chapter(self, chapter: Chapter) -> None:
        """한 챕터를 요약합니다. 컨텍스트 체이닝은 run_batch에서 순차적으로 호출할 수도 있으나, 
        현재는 기본 비동기 큐 구조 유지."""
        
        # [Logic] 이전 화의 요약 찾아오기 (없으면 None)
        prev_summary = self.results.get(chapter.cid - 1) if chapter.cid > 0 else None
        
        await self.rate_limiter.acquire()
        async with self.semaphore:
            retries = 5
            base_delay = 5
            for attempt in range(retries):
                try:
                    summary = await self.client.summarize_async(chapter.body, context=prev_summary)
                    
                    if summary == "[CENSORED_BLOCK]":
                        summary = "🔞 [검열됨] 성인용 콘텐츠 문제로 AI 요약 거부."
                    
                    self.results[chapter.cid] = summary
                    self.completed_cids.append(chapter.cid)
                    if self.checkpoint_manager:
                        self.checkpoint_manager.save(self.completed_cids, self.results)
                    return

                except RateLimitError:
                    wait_time = min(base_delay * (2 ** attempt), 120)
                    await asyncio.sleep(wait_time)
                    continue
                except AIError as e:
                    self.results[chapter.cid] = f"(Error: {e})"
                    return

    async def run_batch(self, chapters: List[Chapter]) -> str:
        self.all_chapters = chapters
        
        # 체크포인트 복구
        if self.checkpoint_manager:
            cids, res = self.checkpoint_manager.load()
            self.completed_cids, self.results = cids, res

        # [Important] 컨텍스트 체이닝을 위해 가급적 순서대로 태스크를 생성하거나 
        # 순차성이 보장되는 큐 방식을 써야 하지만, 
        # 일단 병렬성을 우선하여 as_completed로 처리.
        # (순차 요약이 필수라면 tasks를 루프로 순서대로 기다려야 함)
        
        remaining_chapters = [ch for ch in chapters if ch.cid not in self.completed_cids]
        if not remaining_chapters: return self.generate_report()

        tasks = [self.summarize_chapter(ch) for ch in remaining_chapters]
        for f in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Summarizing", unit="chap"):
            await f
            
        if self.checkpoint_manager: self.checkpoint_manager.clear()
        return self.generate_report()

    def generate_report(self) -> str:
        # cid 순서로 정렬된 결과 반환 (ReportFormatter가 처리)
        return self.formatter.format(self.all_chapters, self.results)

