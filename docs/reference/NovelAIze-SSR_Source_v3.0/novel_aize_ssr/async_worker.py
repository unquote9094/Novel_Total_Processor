import asyncio
import time
from typing import List, Dict, Optional
from tqdm.asyncio import tqdm
from novel_aize_ssr.structure import Chapter
from novel_aize_ssr.gemini_client import GeminiClient
from novel_aize_ssr.checkpoint import CheckpointManager
from novel_aize_ssr.report_formatter import ReportFormatter
from novel_aize_ssr.rate_limiter import RateLimiter

class AsyncSummarizer:
    def __init__(self, api_key: str, concurrency: int = 5, model_name: str = "gemini-3-flash-preview", 
                 genre: str = "general", checkpoint_manager: Optional[CheckpointManager] = None,
                 output_format: str = "plain", rate_limit_rpm: int = 15):
        self.client = GeminiClient(api_key=api_key, model_name=model_name, genre=genre)
        self.semaphore = asyncio.Semaphore(concurrency)
        self.rate_limiter = RateLimiter(rpm=rate_limit_rpm)
        self.results: Dict[int, str] = {}
        self.genre = genre
        self.checkpoint_manager = checkpoint_manager
        self.formatter = ReportFormatter(output_format=output_format)
        self.completed_cids: List[int] = []
        self.all_chapters: List[Chapter] = []  # Store all chapters for report generation
        
    async def summarize_chapter(self, chapter: Chapter) -> None:
        # RateLimiter를 통해 정밀한 속도 제어 (병렬 실행 시에도 순차적 대기 보장)
        await self.rate_limiter.acquire()
        
        async with self.semaphore:
            # 속도 제한(Rate Limit) / 재시도 로직 강화
            retries = 5
            base_delay = 5
            
            for attempt in range(retries):
                try:
                    summary = await self.client.summarize_async(chapter.body)
                    
                    # None/빈 응답 체크 강화
                    if summary is None:
                        summary = "Error: None response"
                    
                    if "Error" in str(summary):
                        # 429 Resource Exhausted (할당량 초과)
                        if "429" in str(summary) or "ResourceExhausted" in str(summary) or "Quota" in str(summary):
                            wait_time = base_delay * (2 ** attempt)  # 더 공격적인 백오프
                            wait_time = min(wait_time, 120)
                            
                            print(f"   ⚠️  [Rate Limit] Chapter {chapter.cid}. {wait_time}초 대기 후 재시도...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # 그 외 에러 (API 호출 실패 등)
                            error_msg = f"API Error ({type(summary)}): {summary}"
                            print(f"   ❌ [Chapter {chapter.cid}] {error_msg}")
                            self.results[chapter.cid] = f"(Failed: {error_msg})"
                            break
                    
                    # [New] Censorship Handling
                    if summary == "[CENSORED_BLOCK]":
                        msg = "🔞 [검열됨] 성인용 선정성/폭력성 문제로 인해 AI가 요약을 거부했습니다."
                        print(f"   🚫 [Chapter {chapter.cid}] {msg}")
                        self.results[chapter.cid] = msg
                        self.completed_cids.append(chapter.cid)
                        
                        # 체크포인트 저장
                        if self.checkpoint_manager:
                            self.checkpoint_manager.save(self.completed_cids, self.results)
                        return

                    self.results[chapter.cid] = summary
                    self.completed_cids.append(chapter.cid)
                    
                    # 체크포인트 저장
                    if self.checkpoint_manager:
                        self.checkpoint_manager.save(self.completed_cids, self.results)
                    
                    return
                    
                except AttributeError as e:
                    # 'NoneType' object has no attribute 'strip' 등
                    print(f"   ⚠️  [Chapter {chapter.cid}] 빈 응답, 재시도 중...")
                    await asyncio.sleep(base_delay)
                    continue
                    
                except Exception as e:
                    error_type = type(e).__name__
                    error_msg = str(e)
                    print(f"   ❌ [Chapter {chapter.cid}] Exception: [{error_type}] {error_msg}")
                    self.results[chapter.cid] = f"(Exception: {error_type} - {error_msg})"
                    return

            self.results[chapter.cid] = "(Failed: Max Retries Exceeded - Rate Limit Too Severe)"

    async def process_all(self, chapters: List[Chapter]) -> str:
        """
        Process all chapters and return a formatted report.
        """
        # Store all chapters for report generation
        self.all_chapters = chapters
        
        # 체크포인트에서 이미 완료된 챕터 불러오기
        remaining_chapters = chapters
        if self.checkpoint_manager:
            completed_cids, saved_results = self.checkpoint_manager.load()
            self.completed_cids = completed_cids
            self.results = saved_results
            
            # 이미 완료된 챕터는 제외
            remaining_chapters = [ch for ch in chapters if ch.cid not in completed_cids]
            
            if not remaining_chapters:
                print("[AsyncWorker] All chapters already completed!")
                return self.generate_report()
            
            print(f"[AsyncWorker] Resuming from checkpoint. {len(remaining_chapters)} chapters remaining.")
        
        tasks = [self.summarize_chapter(ch) for ch in remaining_chapters]
        
        # 비동기 작업을 위한 tqdm 진행바
        # as_completed를 사용하여 진행률 표시
        
        print(f"\n[AsyncWorker] Starting Batch Summarization (Concurrency: {self.semaphore._value})...")
        
        # 전체 태스크 실행 및 진행바
        for f in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Summarizing", unit="chap"):
            await f
            
        # 완료 후 체크포인트 삭제
        if self.checkpoint_manager:
            self.checkpoint_manager.clear()
            
        return self.generate_report()
        
    def generate_report(self) -> str:
        """
        포맷터를 사용하여 리포트 생성 (모든 챕터 포함)
        """
        return self.formatter.format(self.all_chapters, self.results)
