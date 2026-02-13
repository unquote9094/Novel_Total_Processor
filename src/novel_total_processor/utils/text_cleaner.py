"""텍스트 정리 유틸리티

검색 쿼리 및 메타데이터 처리를 위한 텍스트 정리 함수
"""

import re
from typing import Optional
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


def clean_search_title(filename: str) -> str:
    """검색용 제목 정리
    
    파일명에서 불필요한 요소를 제거하고 검색에 적합한 제목만 추출
    
    Args:
        filename: 원본 파일명
    
    Returns:
        정리된 검색용 제목
    
    Examples:
        >>> clean_search_title("#마왕의 딸로 태어났습니다(1~370.연재).txt")
        "마왕의 딸로 태어났습니다"
        
        >>> clean_search_title("회귀했더니_최강검사.epub")
        "회귀했더니 최강검사"
        
        >>> clean_search_title("소설제목_작가명.txt")
        "소설제목 작가명"
    """
    # 1. 파일 확장자 제거
    title = filename
    for ext in ['.txt', '.epub', '.pdf', '.doc', '.docx']:
        if title.lower().endswith(ext):
            title = title[:-len(ext)]
            break
    
    # 2. 선행 해시 마커 제거 (예: #마왕의 딸...)
    title = re.sub(r'^#+\s*', '', title)
    
    # 3. 괄호로 감싼 에피소드/상태 힌트 제거
    # 예: (1~370.연재), (완결), (321화), (1-50), (1~50)
    title = re.sub(r'\([^)]*(?:\d+[~\-]\d+|\d+화|완결|연재|휴재)[^)]*\)', '', title)
    
    # 4. 빈 괄호 제거
    title = re.sub(r'\(\s*\)', '', title)
    
    # 5. 언더스코어를 공백으로 변환
    title = title.replace('_', ' ')
    
    # 6. 다중 공백을 단일 공백으로
    title = re.sub(r'\s+', ' ', title)
    
    # 7. 앞뒤 공백 제거
    title = title.strip()
    
    logger.debug(f"Title cleaned: '{filename}' → '{title}'")
    
    return title


def extract_episode_range_numeric(episode_range: Optional[str]) -> Optional[int]:
    """에피소드 범위에서 숫자 값 추출
    
    Args:
        episode_range: 에피소드 범위 문자열 (예: "1~370화", "321화", "50권")
    
    Returns:
        추출된 최대 에피소드 번호 (없으면 None)
    
    Examples:
        >>> extract_episode_range_numeric("1~370화")
        370
        
        >>> extract_episode_range_numeric("321화")
        321
        
        >>> extract_episode_range_numeric("50권")
        50
    """
    if not episode_range:
        return None
    
    # 범위 형식 (예: 1~370, 1-370)
    range_match = re.search(r'(\d+)[~\-](\d+)', episode_range)
    if range_match:
        return int(range_match.group(2))  # 최대값 반환
    
    # 단일 숫자 형식 (예: 321화, 50권)
    single_match = re.search(r'(\d+)', episode_range)
    if single_match:
        return int(single_match.group(1))
    
    return None
