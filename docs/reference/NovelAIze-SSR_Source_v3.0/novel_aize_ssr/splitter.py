import re
import os
from typing import Generator
from novel_aize_ssr.structure import Chapter

class Splitter:
    """
    Regex 패턴을 사용하여 대용량 텍스트 파일을 챕터 단위로 분할하는 클래스.
    Memory Efficient: Generator 방식을 사용하여 전체 파일을 메모리에 적재하지 않음.
    """
    def __init__(self):
        pass

    def split(self, file_path: str, regex_pattern: str) -> Generator[Chapter, None, None]:
        """
        파일을 스트리밍 방식으로 읽어 챕터를 분할하여 반환(Yield).

        :param file_path: 대상 텍스트 파일 경로
        :param regex_pattern: 챕터 구분에 사용할 정규식 (예: r"제\\s*\\d+\\s*화")
        :yield: Chapter 객체
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            pattern = re.compile(regex_pattern)
        except re.error as e:
            raise ValueError(f"Invalid Regex Pattern: {e}")

        buffer = []
        current_title = "Prologue (Pre-Match)" # 첫 매칭 전까지의 내용은 프롤로그 등으로 취급 가능
        chapter_count = 0
        
        # 인코딩 문제는 추후 chardet 등으로 보강 가능. 지금은 utf-8 가정.
        # errors='replace'로 깨진 문자 무시.
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for line_idx, line in enumerate(f):
                line_stripped = line.strip()
                
                # 정규식으로 챕터 제목인지 확인
                # pattern.search()를 사용하여 줄 전체를 제목으로 사용
                match = pattern.search(line_stripped)
                
                if match:
                    # 이전 챕터가 존재하면 Yield
                    # 단, 버퍼가 비어있지 않거나, 의미 있는 내용이 있을 때만
                    if buffer or chapter_count == 0:
                        body_text = "".join(buffer).strip()
                        
                        # 이전 화 본문 끝에서 제목 패턴이 포함된 줄 제거
                        # 본문에서 제목 패턴이 포함된 마지막 줄을 찾아서 제거
                        body_lines = body_text.splitlines()
                        cleaned_lines = []
                        for body_line in body_lines:
                            if not pattern.search(body_line.strip()):
                                cleaned_lines.append(body_line)
                        body_text = "\n".join(cleaned_lines).strip()
                        
                        # 빈 본문이거나 너무 짧으면 (100자 미만) 이전 챕터와 병합 고려
                        # 첫 번째 챕터가 아닌 경우에만 검사
                        if chapter_count > 0 and len(body_text) < 100:
                            # 너무 짧은 챕터는 스킵 (연속 제목 문제)
                            current_title = line_stripped
                            buffer = []
                            continue
                        
                        yield Chapter(
                            cid=chapter_count,
                            title=current_title,
                            body=body_text,
                            length=len(body_text)
                        )
                        chapter_count += 1
                        # if chapter_count % 50 == 0:
                        #     print(f"[Splitter] Detected {chapter_count} chapters so far...")
                    
                    # 새 챕터 시작 - 매칭된 줄 전체를 제목으로 사용
                    current_title = line_stripped
                    buffer = [] # 버퍼 초기화
                else:
                    # 제목이 아니면 내용에 추가
                    buffer.append(line)

            # 마지막 챕터 처리 (파일 끝 도달 시)
            if buffer:
                body_text = "".join(buffer).strip()
                yield Chapter(
                    cid=chapter_count,
                    title=current_title,
                    body=body_text,
                    length=len(body_text)
                )

    def verify_pattern(self, file_path: str, regex_pattern: str) -> dict:
        """
        패턴이 파일 전체를 커버하는지 검증합니다.
        
        :param file_path: 대상 파일 경로
        :param regex_pattern: 테스트할 정규식
        :return: {'match_count': int, 'last_match_pos': int, 'last_match_ratio': float, 'coverage_ok': bool}
        """
        match_count = 0
        last_match_pos = 0
        total_size = os.path.getsize(file_path)
        
        try:
            pattern = re.compile(regex_pattern)
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
            
            # 보다 엄격한 검증을 위해 93% -> 99%, 50KB -> 20KB로 변경
            coverage_ok = (last_match_ratio > 0.99) or (tail_size < 20000)
            
            print(f"[Splitter Verify] Matches: {match_count}, Coverage: {last_match_ratio*100:.1f}% (Last Pos: {last_match_pos}/{total_size}, Tail: {tail_size/1024:.1f}KB)")
            
            return {
                'match_count': match_count,
                'last_match_pos': last_match_pos,
                'last_match_ratio': last_match_ratio,
                'tail_size': tail_size,
                'coverage_ok': coverage_ok
            }
            
        except Exception as e:
            print(f"[Splitter Verify] Error: {e}")
            return {
                'match_count': 0,
                'last_match_ratio': 0.0,
                'coverage_ok': False
            }
