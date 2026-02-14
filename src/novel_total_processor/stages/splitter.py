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
    """Regex 패턴을 사용하여 대용량 텍스트 파일을 챕터 단위로 분할 (v3.0 Reference)
    
    Enhanced Features:
    - Support for explicit title candidate lines (fallback when regex misses chapters)
    - Multi-line title support (merge title candidate + true title)
    - Aggressive title trimming (20-char threshold for body vs subtitle)
    """
    
    # Multi-line title detection constants
    # BRACKET_PATTERN_LENGTH: Check first 50 chars for bracket patterns to detect multi-line titles
    # This is chosen to cover typical Korean novel title formats like "[웹소설 - 34화]"
    BRACKET_PATTERN_LENGTH = 50
    
    # MAX_TITLE_LENGTH: Limit extracted title to 100 chars to avoid including body text
    # Korean chapter titles rarely exceed this length, and it helps maintain clean separation
    MAX_TITLE_LENGTH = 100
    
    def __init__(self):
        pass  # No instance state needed; all parameters passed to split() method
    
    def split(
        self,
        file_path: str,
        chapter_pattern: str,
        subtitle_pattern: Optional[str] = None,
        encoding: str = 'utf-8',
        title_candidates: Optional[List[str]] = None
    ) -> Generator[Chapter, None, None]:
        """파일을 스트리밍 방식으로 읽어 챕터를 분할 (v3.0 기반 고성능 버전)
        
        Args:
            file_path: Path to file
            chapter_pattern: Regex pattern for chapter titles
            subtitle_pattern: Optional regex pattern for subtitles
            encoding: File encoding
            title_candidates: Optional list of explicit title lines for fallback detection
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            pattern = re.compile(chapter_pattern)
            subtitle_re = re.compile(subtitle_pattern) if subtitle_pattern else None
        except re.error as e:
            raise ValueError(f"Invalid Regex Pattern: {e}")
        
        # When using explicit title_candidates, we should not filter body text aggressively
        # The permissive pattern is only for detection, not for filtering
        using_explicit_titles = bool(title_candidates)
        
        # Debug logging for title_candidates mode
        if using_explicit_titles:
            logger.info(f"   🔍 Splitter: Using {len(title_candidates)} explicit title_candidates")
            logger.info(f"      → Will skip aggressive body text filtering")
            logger.info(f"      → Sample candidates: {title_candidates[:3] if len(title_candidates) > 0 else []}")
        
        buffer = []
        current_title = ""
        current_subtitle = ""
        chapter_count = 0
        first_match_found = False
        
        # Multi-line title support: track potential title candidates
        pending_title_candidate = None
        
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            for line_idx, line in enumerate(f):
                line_stripped = line.strip()
                if not line_stripped:
                    if first_match_found: buffer.append(line)
                    pending_title_candidate = None  # Reset on blank line
                    continue
                
                # Check if this line is in explicit title candidates
                is_explicit_title = (title_candidates and 
                                   any(line_stripped == candidate or 
                                       candidate in line_stripped 
                                       for candidate in title_candidates))
                
                # Debug logging for explicit title detection
                if using_explicit_titles and is_explicit_title:
                    logger.info(f"   ✓ Matched explicit title at line {line_idx}: '{line_stripped[:50]}'")
                
                # 정규식 매칭 (제목 여부 확인) or explicit title
                match = pattern.search(line_stripped)
                
                # When using explicit titles, ONLY use explicit title matching
                # The pattern is permissive and would match everything otherwise
                if using_explicit_titles:
                    is_chapter_boundary = is_explicit_title
                else:
                    is_chapter_boundary = match or is_explicit_title
                
                if is_chapter_boundary:
                    # Check for multi-line title pattern
                    # If we have a pending candidate and this is also a match,
                    # merge them into one title
                    if pending_title_candidate and first_match_found:
                        # This is a true title following a candidate
                        # Merge them: "candidate + true_title"
                        merged_title = f"{pending_title_candidate} | {line_stripped[:self.MAX_TITLE_LENGTH].strip()}"
                        pending_title_candidate = None
                        
                        # Use merged title as current title
                        current_title = merged_title
                        buffer = []
                        continue
                    
                    # 1. 이전 챕터 반환 (Yield)
                    if first_match_found:
                        body_text = "".join(buffer).strip()
                        
                        # 본문 내 불필요한 제목 패턴 라인 제거
                        # IMPORTANT: When using explicit title_candidates with permissive pattern,
                        # skip this filtering to avoid removing all body text
                        if not using_explicit_titles:
                            body_lines = body_text.splitlines()
                            body_text = "\n".join([bl for bl in body_lines if not pattern.search(bl.strip())]).strip()
                        
                        # [M-45] 가짜 챕터 가드 (번호 없는 초단문 병합)
                        # IMPORTANT: Skip this guard when using explicit title_candidates
                        # The boundaries from advanced pipeline are already validated
                        if not using_explicit_titles and len(body_text) < 100 and not re.search(r'\d+', current_title):
                            buffer = [f"\n{current_title}\n", body_text + "\n"]
                            if using_explicit_titles:
                                logger.info(f"   ⚠️  Merging short chapter (< 100 chars, no number): '{current_title[:30]}'")
                        else:
                            if body_text:
                                if using_explicit_titles:
                                    logger.info(f"   ✅ Yielding chapter {chapter_count+1}: '{current_title[:30]}' ({len(body_text)} chars)")
                                yield Chapter(
                                    cid=chapter_count,
                                    title=current_title,
                                    subtitle=current_subtitle,
                                    body=body_text,
                                    length=len(body_text)
                                )
                                chapter_count += 1
                            elif using_explicit_titles:
                                logger.info(f"   ⚠️  Skipping empty chapter: '{current_title[:30]}'")

                    # 2. 새 챕터 시작 - Aggressive Title Trimming (Ref-v3.0 고도화)
                    first_match_found = True
                    
                    # [Smart Trimming] 제목 뒤에 본문이 딸려오는 현상 차단
                    # When using explicit titles, we already have the exact title text
                    if using_explicit_titles:
                        # Use the exact title from candidates - no trimming needed
                        current_title = line_stripped[:self.MAX_TITLE_LENGTH].strip()
                        buffer = []
                        current_subtitle = ""
                    elif match:
                        core_match_text = line_stripped[:match.end()].strip()
                        tail_text = line_stripped[match.end():].strip()
                        
                        # 제목 뒷부분이 20자를 넘으면 100% 본문으로 간주 (v3.0 개선안)
                        if len(tail_text) > 20:
                            current_title = core_match_text
                            buffer = [tail_text + "\n"]
                        else:
                            # 20자 이내인 경우에만 부제목으로 인정
                            # Check if this might be a title candidate (for multi-line support)
                            # Bracket patterns within first N chars indicate potential multi-line title
                            if re.search(r'\[.*?\]', line_stripped[:self.BRACKET_PATTERN_LENGTH]):
                                pending_title_candidate = line_stripped[:self.MAX_TITLE_LENGTH].strip()
                            
                            current_title = line_stripped[:self.MAX_TITLE_LENGTH].strip()
                            buffer = []
                        
                        current_subtitle = ""
                    else:
                        # Explicit title candidate (old path, shouldn't reach here anymore)
                        current_title = line_stripped[:self.MAX_TITLE_LENGTH].strip()
                        buffer = []
                        current_subtitle = ""
                    
                    continue
                
                elif first_match_found:
                    buffer.append(line)
                    pending_title_candidate = None  # Reset if we see body text
            
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
