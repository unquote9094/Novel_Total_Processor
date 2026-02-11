from dataclasses import dataclass

@dataclass
class Chapter:
    """
    소설의 한 챕터를 나타내는 데이터 클래스.
    """
    cid: int          # 챕터 순서 (Index)
    title: str        # 챕터 제목 (예: "제 1 화")
    body: str         # 챕터 본문 내용
    length: int       # 본문 글자 수 (공백 포함)

    def __repr__(self):
        return f"<Chapter {self.cid}: {self.title} ({self.length} chars)>"
