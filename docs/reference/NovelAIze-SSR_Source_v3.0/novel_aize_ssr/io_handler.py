import os
from typing import Generator, Iterator, Optional
from novel_aize_ssr.structure import Chapter
from novel_aize_ssr.sampler import Sampler
from novel_aize_ssr.reformatter import Reformatter
from tqdm import tqdm

class IOHandler:
    """
    파일 입출력, 샘플링, 스트리밍 쓰기를 전담하는 클래스.
    Sampler와 write_stream 로직을 하나로 관리합니다.
    """
    def __init__(self):
        self.sampler = Sampler()
        self.reformatter = Reformatter()

    def extract_samples(self, file_path: str) -> str:
        """분산형 샘플 추출"""
        return self.sampler.extract_samples(file_path)

    def extract_samples_from(self, file_path: str, offset: int) -> str:
        """특정 위치 이후 샘플 추출 (재시도용)"""
        return self.sampler.extract_samples_from(file_path, offset)

    def write_chapters_stream(self, chapters: Iterator[Chapter], 
                              output_path: str, 
                              total_chapters: Optional[int] = None):
        """챕터 스트림을 파일로 저장 (Reformat 적용)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            pbar = tqdm(chapters, total=total_chapters, desc="Writing", unit="chap")
            chapter_count = 0
            for chapter in pbar:
                formatted_text = self.reformatter.beautify(chapter)
                f.write(formatted_text)
                chapter_count += 1
        return chapter_count

    @staticmethod
    def save_report(report_content: str, output_path: str):
        """요약 리포트 저장"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
