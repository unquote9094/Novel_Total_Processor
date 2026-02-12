"""챕터 데이터 구조

소설의 챕터를 나타내는 데이터 클래스
"""

from dataclasses import dataclass


@dataclass
class Chapter:
    """소설의 한 챕터
    
    Attributes:
        cid: 챕터 순서 (Index)
        title: 챕터 제목 (예: "아포칼립스에 집을 숨김 147화")
        subtitle: 챕터 소제목/부제목 (예: "73. 완장 (5)")
        body: 챕터 본문 내용
        length: 본문 글자 수 (공백 포함)
        chapter_type: 챕터 유형 (본편/외전/에필로그/후일담/작가의말)
    """
    cid: int
    title: str
    subtitle: str
    body: str
    length: int
    chapter_type: str = "본편"
    
    def __repr__(self):
        return f"<Chapter {self.cid}: {self.title} ({self.length} chars, type={self.chapter_type})>"
