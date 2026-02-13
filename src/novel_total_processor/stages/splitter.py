"""텍스트 분할기 (Reference v3.0 기반 고도화)

Regex 패턴을 사용하여 대용량 텍스트 파일을 챕터 단위로 분할
Aggressive Title Trimming: 제목과 본문의 엄격한 분리 (20자 기준)
"""

import re
import os
from typing import Generator, Tuple, Optional, List
from novel_total_processor.stages.chapter import Chapter
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


class Splitter:
    """Regex 패턴을 사용하여 대용량 텍스트 파일을 챕터 단위로 분할 (v3.0 Reference)"""
    
    def __init__(self):
        pass
    
    def split(
        self,
        file_path: str,
        chapter_pattern: str,
        subtitle_pattern: Optional[str] = None,
        encoding: str = 'utf-8'
    ) -> Generator[Chapter, None, None]:
        """파일을 스트리밍 방식으로 읽어 챕터를 분할 (v3.0 기반 고성능 버전)"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            pattern = re.compile(chapter_pattern)
            subtitle_re = re.compile(subtitle_pattern) if subtitle_pattern else None
        except re.error as e:
            raise ValueError(f"Invalid Regex Pattern: {e}")
        
        buffer = []
        current_title = ""
        current_subtitle = ""
        chapter_count = 0
        first_match_found = False
        
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            for line_idx, line in enumerate(f):
                line_stripped = line.strip()
                if not line_stripped:
                    if first_match_found: buffer.append(line)
                    continue
                
                # 정규식 매칭 (제목 여부 확인)
                match = pattern.search(line_stripped)
                
                if match:
                    # 1. 이전 챕터 반환 (Yield)
                    if first_match_found:
                        body_text = "".join(buffer).strip()
                        
                        # 본문 내 불필요한 제목 패턴 라인 제거
                        body_lines = body_text.splitlines()
                        body_text = "\n".join([bl for bl in body_lines if not pattern.search(bl.strip())]).strip()
                        
                        # [M-45] 가짜 챕터 가드 (번호 없는 초단문 병합)
                        if len(body_text) < 100 and not re.search(r'\d+', current_title):
                            buffer = [f"\n{current_title}\n", body_text + "\n"]
                        else:
                            if body_text:
                                yield Chapter(
                                    cid=chapter_count,
                                    title=current_title,
                                    subtitle=current_subtitle,
                                    body=body_text,
                                    length=len(body_text)
                                )
                                chapter_count += 1

                    # 2. 새 챕터 시작 - Aggressive Title Trimming (Ref-v3.0 고도화)
                    first_match_found = True
                    
                    # [Smart Trimming] 제목 뒤에 본문이 딸려오는 현상 차단
                    core_match_text = line_stripped[:match.end()].strip()
                    tail_text = line_stripped[match.end():].strip()
                    
                    # 제목 뒷부분이 20자를 넘으면 100% 본문으로 간주 (v3.0 개선안)
                    if len(tail_text) > 20:
                        current_title = core_match_text
                        buffer = [tail_text + "\n"]
                    else:
                        # 20자 이내인 경우에만 부제목으로 인정
                        current_title = line_stripped[:100].strip()
                        buffer = []
                    
                    current_subtitle = ""
                    continue
                
                elif first_match_found:
                    buffer.append(line)
            
            # 마지막 챕터 처리
            if first_match_found:
                body_text = "".join(buffer).strip()
                if body_text:
                    yield Chapter(
                        cid=chapter_count,
                        title=current_title,
                        subtitle=current_subtitle,
                        body=body_text,
                        length=len(body_text)
                    )

    def verify_pattern(self, file_path: str, chapter_pattern: str, encoding: str = 'utf-8') -> dict:
        """패턴 검증 (Reference v3.0의 엄격한 커버리지 기준 적용)"""
        match_count = 0
        last_match_pos = 0
        total_size = os.path.getsize(file_path)
        try:
            pattern = re.compile(chapter_pattern)
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                while True:
                    pos = f.tell()
                    line = f.readline()
                    if not line: break
                    if pattern.search(line.strip()):
                        match_count += 1
                        last_match_pos = pos
            
            # v3.0 기준: 99% 커버리지 또는 잔여 20KB 미만 성공
            last_match_ratio = last_match_pos / total_size if total_size > 0 else 0
            tail_size = total_size - last_match_pos
            coverage_ok = (last_match_ratio > 0.99) or (tail_size < 20000)
            
            return {
                'match_count': match_count,
                'last_match_pos': last_match_pos,
                'last_match_ratio': last_match_ratio,
                'tail_size': tail_size,
                'coverage_ok': coverage_ok
            }
        except Exception as e:
            logger.error(f"Pattern verification error: {e}")
            return {
                'match_count': 0,
                'last_match_pos': 0,
                'last_match_ratio': 0.0,
                'tail_size': total_size,
                'coverage_ok': False
            }

    def find_matches_with_pos(self, file_path: str, chapter_pattern: str, encoding: str = 'utf-8') -> list:
        matches = []
        try:
            pattern = re.compile(chapter_pattern)
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                while True:
                    pos = f.tell()
                    line = f.readline()
                    if not line: break
                    if pattern.search(line.strip()):
                        matches.append({'pos': pos, 'line': line.strip()})
            return matches
        except: return []

    def find_large_gaps(self, file_path: str, matches: list) -> list:
        if not matches: return []
        total_size = os.path.getsize(file_path)
        gaps = []
        if matches[0]['pos'] > 50000:
            gaps.append({'start': 0, 'end': matches[0]['pos'], 'size': matches[0]['pos']})
        for i in range(len(matches)-1):
            size = matches[i+1]['pos'] - matches[i]['pos']
            if size > 100000: # 100KB 이상 갭 추적
                gaps.append({'start': matches[i]['pos'], 'end': matches[i+1]['pos'], 'size': size})
        
        tail_size = total_size - matches[-1]['pos']
        if tail_size > 50000:
            gaps.append({'start': matches[-1]['pos'], 'end': total_size, 'size': tail_size})
            
        gaps.sort(key=lambda x: x['size'], reverse=True)
        return gaps[:5]
