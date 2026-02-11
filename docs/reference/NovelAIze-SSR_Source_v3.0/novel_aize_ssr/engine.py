import os
import time
import asyncio
from typing import Optional, Dict, Any

from novel_aize_ssr.config import load_config
from novel_aize_ssr.sampler import Sampler
from novel_aize_ssr.pattern_manager import PatternManager
from novel_aize_ssr.splitter import Splitter
from novel_aize_ssr.summarize_manager import SummarizeManager
from novel_aize_ssr.checkpoint import CheckpointManager
from novel_aize_ssr.ui_helper import UIHelper

class NovelEngine:
    """
    NovelAIze-SSR의 모든 기능을 엮어주는 중앙 오케스트레이션 엔진.
    이 클래스 하나로 소설 분석, 분할, 요약 과정을 모두 실행할 수 있습니다.
    """
    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        self.config = load_config()
        if config_override:
            self.config.update(config_override)
            
        self.sampler = Sampler()
        self.splitter = Splitter()
        
    async def run(self, input_path: str, mode: str = "preview", 
                  genre: str = "general", output_format: str = "plain",
                  resume: bool = False) -> Dict[str, Any]:
        """
        전체 프로세스 실행 로직.
        :param input_path: 소설 파일 경로
        :param mode: 'format' (정리만), 'summarize' (요약 포함), 'preview' (미리보기)
        :param genre: 장르 프롬프트
        :param output_format: 리포트 형식
        :param resume: 체크포인트 소환 여부
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"File not found: {input_path}")
            
        start_time = time.time()
        results = {"success": False, "total_time": 0}
        
        # 1. 샘플링
        samples = self.sampler.extract_samples(input_path)
        
        # 2. AI 클라이언트 및 패턴 매니저 준비
        api_key = self.config.get("api_key")
        from novel_aize_ssr.gemini_client import GeminiClient
        client = GeminiClient(api_key=api_key, 
                              model_name=self.config.get("model_name"), 
                              genre=genre)
        
        pm = PatternManager(client)
        
        # 3. 최적 패턴 탐색 (Adaptive Retry 포함)
        pattern = pm.find_best_pattern(input_path, samples)
        if not pattern:
            results["error"] = "Could not identify a reliable chapter pattern."
            return results
        
        # 4. 챕터 분할
        chapters = list(self.splitter.split(input_path, pattern))
        total_chapters = len(chapters)
        
        # 5. 모드별 동작
        if mode == "preview":
            results.update({"success": True, "chapters": chapters[:5], "total": total_chapters, "pattern": pattern})
            
        elif mode == "format":
            from novel_aize_ssr.file_io import write_stream
            base, ext = os.path.splitext(input_path)
            output_file = f"{base}_formatted{ext}"
            
            # Generator for write_stream
            def ch_gen():
                for ch in chapters: yield ch
                
            write_stream(ch_gen(), output_file, total_chapters)
            results.update({"success": True, "output_file": output_file, "total": total_chapters})
            
        elif mode == "summarize":
            checkpoint_mgr = CheckpointManager(input_path) if resume else None
            sm = SummarizeManager(
                api_key=api_key,
                concurrency=self.config.get("concurrency", 5),
                model_name=self.config.get("model_name"),
                genre=genre,
                checkpoint_manager=checkpoint_mgr,
                output_format=output_format,
                rate_limit_rpm=self.config.get("rate_limit_rpm", 15)
            )
            
            report = await sm.run_batch(chapters)
            
            # 리포트 저장
            base, ext = os.path.splitext(input_path)
            ext_map = {"json": ".json", "markdown": ".md", "plain": ".txt"}
            output_file = f"{base}_summary{ext_map.get(output_format, '.txt')}"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
                
            results.update({"success": True, "output_file": output_file, "total": total_chapters})
            
        results["total_time"] = time.time() - start_time
        return results
