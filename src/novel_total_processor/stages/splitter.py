"""텍스트 분할기

Regex 패턴을 사용하여 대용량 텍스트 파일을 챕터 단위로 분할
NovelAIze-SSR v3.0의 Splitter 클래스 포팅 + 소제목 추출 기능 추가
"""

import re
import os
from typing import Generator, Tuple, Optional
from novel_total_processor.stages.chapter import Chapter
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


class Splitter:
    """Regex 패턴을 사용하여 대용량 텍스트 파일을 챕터 단위로 분할하는 클래스
    
    Memory Efficient: Generator 방식을 사용하여 전체 파일을 메모리에 적재하지 않음
    """
    
    def __init__(self):
        pass
    
    def split(
        self,
        file_path: str,
        chapter_pattern: str,
        subtitle_pattern: Optional[str] = None
    ) -> Generator[Chapter, None, None]:
        """파일을 스트리밍 방식으로 읽어 챕터를 분할하여 반환(Yield)
        
        Args:
            file_path: 대상 텍스트 파일 경로
            chapter_pattern: 챕터 구분에 사용할 정규식 (예: r"━+\s*.*?\s*\d+화\s*━+")
            subtitle_pattern: 챕터 소제목 정규식 (예: r"^\d+\.\s*.+$")
        
        Yields:
            Chapter 객체
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            pattern = re.compile(chapter_pattern)
            subtitle_re = re.compile(subtitle_pattern) if subtitle_pattern else None
        except re.error as e:
            raise ValueError(f"Invalid Regex Pattern: {e}")
        
        buffer = []
        current_title = "Prologue (Pre-Match)"  # 첫 매칭 전까지의 내용은 프롤로그 등으로 취급
        current_subtitle = ""
        chapter_count = 0
        
        # 인코딩 문제는 chardet으로 보강 가능. 지금은 utf-8 가정
        # errors='replace'로 깨진 문자 무시
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for line_idx, line in enumerate(f):
                line_stripped = line.strip()
                
                # 정규식으로 챕터 제목인지 확인
                match = pattern.search(line_stripped)
                
                if match:
                    # 이전 챕터가 존재하면 Yield
                    if buffer or chapter_count == 0:
                        body_text = "".join(buffer).strip()
                        
                        # 본문에서 제목 패턴이 포함된 줄 제거
                        body_lines = body_text.splitlines()
                        cleaned_lines = []
                        for body_line in body_lines:
                            if not pattern.search(body_line.strip()):
                                cleaned_lines.append(body_line)
                        body_text = "\n".join(cleaned_lines).strip()
                        
                        # 빈 본문이거나 너무 짧으면 (100자 미만) 이전 챕터와 병합 고려
                        if chapter_count > 0 and len(body_text) < 100:
                            # 너무 짧은 챕터는 스킵 (연속 제목 문제)
                            current_title = line_stripped
                            buffer = []
                            continue
                        
                        yield Chapter(
                            cid=chapter_count,
                            title=current_title,
                            subtitle=current_subtitle,
                            body=body_text,
                            length=len(body_text)
                        )
                        chapter_count += 1
                    
                    # 새 챕터 시작 - 매칭된 줄 전체를 제목으로 사용
                    current_title = line_stripped
                    current_subtitle = ""
                    buffer = []
                
                elif subtitle_re and subtitle_re.search(line_stripped):
                    # 소제목 감지 (챕터 제목 다음 라인에서 주로 발견됨)
                    if not current_subtitle:  # 첫 번째 소제목만 저장
                        current_subtitle = line_stripped
                    buffer.append(line)
                
                else:
                    # 제목이 아니면 내용에 추가
                    buffer.append(line)
            
            # 마지막 챕터 처리 (파일 끝 도달 시)
            if buffer:
                body_text = "".join(buffer).strip()
                yield Chapter(
                    cid=chapter_count,
                    title=current_title,
                    subtitle=current_subtitle,
                    body=body_text,
                    length=len(body_text)
                )
    
    def verify_pattern(self, file_path: str, chapter_pattern: str) -> dict:
        """패턴이 파일 전체를 커버하는지 검증
        
        Args:
            file_path: 대상 파일 경로
            chapter_pattern: 테스트할 정규식
        
        Returns:
            {'match_count': int, 'last_match_pos': int, 'last_match_ratio': float, 
             'tail_size': int, 'coverage_ok': bool}
        """
        match_count = 0
        last_match_pos = 0
        total_size = os.path.getsize(file_path)
        
        try:
            pattern = re.compile(chapter_pattern)
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                # 파일 포인터 위치 추적하며 읽기
                while True:
                    pos = f.tell()
                    line = f.readline()
                    if not line:
                        break
                    
                    if pattern.search(line.strip()):
                        match_count += 1
                        last_match_pos = pos
            
            # 마지막 매칭 위치가 파일의 99% 이상 지점인지 확인
            # 단, 남은 용량이 20KB 이상이면 (에필로그 등 누락 가능성) 실패로 간주
            last_match_ratio = last_match_pos / total_size if total_size > 0 else 0.0
            tail_size = total_size - last_match_pos
            
            # 99% 커버리지 또는 tail 20KB 미만
            coverage_ok = (last_match_ratio > 0.99) or (tail_size < 20000)
            
            logger.debug(
                f"[Splitter Verify] Matches: {match_count}, "
                f"Coverage: {last_match_ratio*100:.1f}% "
                f"(Last Pos: {last_match_pos}/{total_size}, Tail: {tail_size/1024:.1f}KB)"
            )
            
            return {
                'match_count': match_count,
                'last_match_pos': last_match_pos,
                'last_match_ratio': last_match_ratio,
                'tail_size': tail_size,
                'coverage_ok': coverage_ok
            }
        
        except Exception as e:
            logger.error(f"[Splitter Verify] Error: {e}")
            return {
                'match_count': 0,
                'last_match_ratio': 0.0,
                'coverage_ok': False,
                'tail_size': total_size
            }
