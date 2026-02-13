"""메타데이터 병합 로직 테스트

_merge_metadata 함수의 우선순위 로직 검증
"""

from novel_total_processor.ai.gemini_client import NovelMetadata
from novel_total_processor.db.schema import get_database
from novel_total_processor.stages.stage1_metadata import MetadataCollector


def test_merge_platform_priority():
    """플랫폼 우선순위 테스트"""
    db = get_database()
    collector = MetadataCollector(db)
    
    # 기본 메타데이터 (낮은 우선순위 플랫폼)
    base = NovelMetadata(
        title="테스트 소설",
        author="작가1",
        genre="판타지",
        platform="조아라",
        last_updated="2024-01-01"
    )
    
    # 추가 정보 (높은 우선순위 플랫폼)
    extra = {
        "title": "테스트 소설",
        "author": "작가2",
        "platform": "노벨피아",
        "last_updated": "2024-01-01"
    }
    
    merged = collector._merge_metadata(base, extra)
    
    # 플랫폼 우선순위가 높은 쪽의 작가 정보가 선택되어야 함
    assert merged.author == "작가2", f"Expected '작가2' but got '{merged.author}'"
    assert merged.platform == "노벨피아", f"Expected '노벨피아' but got '{merged.platform}'"
    
    print("✅ Platform priority test passed!")
    db.close()


def test_merge_episode_range():
    """에피소드 범위 병합 테스트"""
    db = get_database()
    collector = MetadataCollector(db)
    
    # 기본 메타데이터 (작은 에피소드 수)
    base = NovelMetadata(
        title="테스트 소설",
        author="작가",
        genre="판타지",
        episode_range="1~100화",
        platform="리디"
    )
    
    # 추가 정보 (큰 에피소드 수)
    extra = {
        "episode_range": "1~200화",
        "platform": "리디"
    }
    
    merged = collector._merge_metadata(base, extra)
    
    # 더 큰 에피소드 수가 선택되어야 함
    assert merged.episode_range == "1~200화", f"Expected '1~200화' but got '{merged.episode_range}'"
    
    print("✅ Episode range merge test passed!")
    db.close()


def test_merge_newer_date():
    """최신 날짜 우선 테스트"""
    db = get_database()
    collector = MetadataCollector(db)
    
    # 기본 메타데이터 (오래된 날짜)
    base = NovelMetadata(
        title="테스트 소설",
        author="작가",
        genre="판타지",
        last_updated="2024-01-01",
        platform="리디"
    )
    
    # 추가 정보 (최신 날짜)
    extra = {
        "last_updated": "2024-06-01",
        "platform": "리디"
    }
    
    merged = collector._merge_metadata(base, extra)
    
    # 더 최신 날짜가 선택되어야 함
    assert merged.last_updated == "2024-06-01", f"Expected '2024-06-01' but got '{merged.last_updated}'"
    
    print("✅ Newer date test passed!")
    db.close()


def test_merge_genre_combination():
    """장르 병합 테스트"""
    db = get_database()
    collector = MetadataCollector(db)
    
    # 기본 메타데이터
    base = NovelMetadata(
        title="테스트 소설",
        author="작가",
        genre="판타지",
        platform="리디"
    )
    
    # 추가 정보 (다른 장르)
    extra = {
        "genre": "로맨스",
        "platform": "리디"
    }
    
    merged = collector._merge_metadata(base, extra)
    
    # 두 장르가 모두 포함되어야 함
    assert "판타지" in merged.genre, f"Expected '판타지' in genre but got '{merged.genre}'"
    assert "로맨스" in merged.genre, f"Expected '로맨스' in genre but got '{merged.genre}'"
    
    print("✅ Genre combination test passed!")
    db.close()


def main():
    """테스트 실행"""
    print("=" * 50)
    print("Metadata Merge Logic Tests")
    print("=" * 50)
    
    test_merge_platform_priority()
    test_merge_episode_range()
    test_merge_newer_date()
    test_merge_genre_combination()
    
    print("=" * 50)
    print("✅ All merge tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
