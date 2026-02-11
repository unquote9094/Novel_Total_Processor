import re
from novel_aize_ssr.structure import Chapter

class Reformatter:
    """
    챕터의 제목과 본문을 보기 좋게 다듬는 클래스.
    """
    def __init__(self):
        pass

    def beautify(self, chapter: Chapter) -> str:
        """
        Chapter 객체를 받아 포맷팅된 문자열로 반환.
        """
        # 1. 제목 장식 - 박스 형태로 개선
        title = chapter.title.strip()
        
        # 제목에서 숫자+화 패턴 찾아서 하이픈 추가
        # "소설제목15화" → "소설제목 - 15화"
        # "소설제목-15화" → "소설제목 - 15화" (이미 하이픈 있으면 정리)
        title = re.sub(r'([가-힣a-zA-Z])[-]?(\d+화)', r'\1 - \2', title)
        
        line_width = 60
        separator = "━" * line_width
        title_centered = title.center(line_width)
        
        formatted_title = f"\n\n\n\n\n\n\n{separator}\n{title_centered}\n{separator}\n\n\n"

        # 2. 본문 정제
        # - 각 줄의 끝 공백 제거
        # - 연속된 빈 줄(3개 이상)을 2개로 축소
        clean_body = []
        lines = chapter.body.splitlines()
        
        empty_line_count = 0
        
        for line in lines:
            stripped = line.rstrip()
            if not stripped:
                empty_line_count += 1
            else:
                empty_line_count = 0
            
            # 빈 줄은 최대 2개까지만 허용
            if empty_line_count <= 2:
                clean_body.append(stripped)

        formatted_body = "\n".join(clean_body)
        
        # 문단 시작 들여쓰기 (옵션, 일단은 적용 안함 or 필요시 공백 추가)
        # formatted_body = formatted_body.replace("\n", "\n    ") 

        return formatted_title + formatted_body + "\n"
