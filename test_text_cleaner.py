"""텍스트 정리 유틸리티 테스트

clean_search_title 및 extract_episode_range_numeric 함수 검증
"""

from novel_total_processor.utils.text_cleaner import clean_search_title, extract_episode_range_numeric


def test_clean_search_title():
    """검색 제목 정리 테스트"""
    
    # 1. 파일 확장자 제거
    assert clean_search_title("마왕의 딸로 태어났습니다.txt") == "마왕의 딸로 태어났습니다"
    assert clean_search_title("회귀했더니_최강검사.epub") == "회귀했더니 최강검사"
    
    # 2. 해시 마커 제거
    assert clean_search_title("#마왕의 딸로 태어났습니다.txt") == "마왕의 딸로 태어났습니다"
    assert clean_search_title("##소설제목.txt") == "소설제목"
    
    # 3. 에피소드 힌트 제거
    assert clean_search_title("마왕의 딸로 태어났습니다(1~370.연재).txt") == "마왕의 딸로 태어났습니다"
    assert clean_search_title("소설제목(완결).txt") == "소설제목"
    assert clean_search_title("소설제목(321화).txt") == "소설제목"
    assert clean_search_title("소설제목(1-50).txt") == "소설제목"
    
    # 4. 언더스코어를 공백으로
    assert clean_search_title("회귀했더니_최강검사.txt") == "회귀했더니 최강검사"
    assert clean_search_title("소설_제목_테스트.txt") == "소설 제목 테스트"
    
    # 5. 복합 케이스
    assert clean_search_title("#마왕의_딸로_태어났습니다(1~370.연재).txt") == "마왕의 딸로 태어났습니다"
    assert clean_search_title("##소설_제목(완결).epub") == "소설 제목"
    
    # 6. 다중 공백 정리
    assert clean_search_title("소설   제목   테스트.txt") == "소설 제목 테스트"
    
    print("✅ All clean_search_title tests passed!")


def test_extract_episode_range_numeric():
    """에피소드 범위 숫자 추출 테스트"""
    
    # 범위 형식
    assert extract_episode_range_numeric("1~370화") == 370
    assert extract_episode_range_numeric("1-370화") == 370
    assert extract_episode_range_numeric("50~100") == 100
    
    # 단일 숫자 형식
    assert extract_episode_range_numeric("321화") == 321
    assert extract_episode_range_numeric("50권") == 50
    assert extract_episode_range_numeric("100") == 100
    
    # 없거나 유효하지 않은 경우
    assert extract_episode_range_numeric(None) is None
    assert extract_episode_range_numeric("") is None
    assert extract_episode_range_numeric("완결") is None
    
    # 복잡한 형식
    assert extract_episode_range_numeric("총 1~370화") == 370
    assert extract_episode_range_numeric("에피소드 321화") == 321
    
    print("✅ All extract_episode_range_numeric tests passed!")


def main():
    """테스트 실행"""
    print("=" * 50)
    print("Text Cleaner Utility Tests")
    print("=" * 50)
    
    test_clean_search_title()
    test_extract_episode_range_numeric()
    
    print("=" * 50)
    print("✅ All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
