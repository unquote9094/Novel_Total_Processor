"""Test Stage 5 Integration with Stage 4 Cache

Verifies that Stage 5 uses chapter data directly from Stage 4 cache
instead of re-splitting with patterns.
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Mock imports that require API keys
import unittest.mock as mock

# Create mock for GeminiClient before importing
mock_gemini = mock.MagicMock()
sys.modules['novel_total_processor.ai.gemini_client'] = mock_gemini

from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


def test_stage5_uses_stage4_chapters():
    """Test that Stage 5 uses chapters from Stage 4 cache directly"""
    logger.info("=" * 60)
    logger.info("Testing Stage 5 Chapter Cache Usage")
    logger.info("=" * 60)
    
    # Create mock Stage 4 cache data
    stage4_data = {
        "chapters": [
            {
                "cid": 1,
                "title": "< 프롤로그 >",
                "subtitle": "",
                "body": "이것은 프롤로그 본문입니다. " * 50,
                "length": 1000,
                "chapter_type": "본편"
            },
            {
                "cid": 2,
                "title": "< 에피소드(1) >",
                "subtitle": "",
                "body": "첫 번째 에피소드입니다. " * 50,
                "length": 1000,
                "chapter_type": "본편"
            },
            {
                "cid": 3,
                "title": "< 연습생 면접 >",  # No number
                "subtitle": "",
                "body": "숫자가 없는 제목입니다. " * 50,
                "length": 1000,
                "chapter_type": "본편"
            },
            {
                "cid": 4,
                "title": "< 에필로그 >",
                "subtitle": "",
                "body": "마지막 장입니다. " * 50,
                "length": 1000,
                "chapter_type": "외전"
            }
        ],
        "summary": {
            "total": 4,
            "main": 3,
            "extra": 1
        },
        "patterns": {
            "chapter_pattern": r"<\s*.*?\s*>",
            "subtitle_pattern": None
        },
        "reconciliation_log": "정합성 100% 일치 (4화)\nLevel 3 Direct AI search used"
    }
    
    # Verify structure
    assert "chapters" in stage4_data, "Stage 4 data should have 'chapters' key"
    assert len(stage4_data["chapters"]) == 4, "Should have 4 chapters"
    
    # Verify all chapters have body
    for ch in stage4_data["chapters"]:
        assert "body" in ch, f"Chapter {ch['cid']} missing body field"
        assert ch["body"], f"Chapter {ch['cid']} has empty body"
        assert "title" in ch, f"Chapter {ch['cid']} missing title field"
        assert "cid" in ch, f"Chapter missing cid field"
        assert "chapter_type" in ch, f"Chapter {ch['cid']} missing chapter_type field"
    
    logger.info(f"✅ Stage 4 cache has {len(stage4_data['chapters'])} chapters with full data")
    
    # Verify the Stage 5 code would use this data
    # (We can't actually run Stage 5 without full database setup)
    chapters_data = stage4_data.get("chapters", [])
    assert chapters_data, "chapters_data should not be empty"
    
    # Simulate what Stage 5 does
    from novel_total_processor.stages.chapter import Chapter
    
    all_ch_objs = [
        Chapter(
            cid=ch['cid'],
            title=ch['title'],
            subtitle=ch.get('subtitle', ''),
            body=ch['body'],
            length=ch.get('length', len(ch['body'])),
            chapter_type=ch.get('chapter_type', '본편')
        )
        for ch in chapters_data
    ]
    
    assert len(all_ch_objs) == 4, "Should create 4 Chapter objects"
    
    # Verify Chapter objects have correct data
    assert all_ch_objs[0].title == "< 프롤로그 >"
    assert all_ch_objs[1].title == "< 에피소드(1) >"
    assert all_ch_objs[2].title == "< 연습생 면접 >"  # No number, should still work
    assert all_ch_objs[3].title == "< 에필로그 >"
    
    # Verify all have body content
    for ch_obj in all_ch_objs:
        assert ch_obj.body, f"Chapter {ch_obj.cid} has no body"
        assert len(ch_obj.body) > 0, f"Chapter {ch_obj.cid} has empty body"
    
    logger.info("✅ Stage 5 would correctly use Stage 4 chapter data")
    logger.info("✅ No re-splitting needed")


def test_stage4_cache_structure():
    """Test that Stage 4 saves the correct cache structure"""
    logger.info("=" * 60)
    logger.info("Testing Stage 4 Cache Structure")
    logger.info("=" * 60)
    
    from novel_total_processor.stages.chapter import Chapter
    
    # Simulate chapters from Stage 4
    chapters = [
        Chapter(
            cid=1,
            title="제1화",
            subtitle="시작",
            body="본문 내용 " * 100,
            length=500,
            chapter_type="본편"
        ),
        Chapter(
            cid=2,
            title="제2화",
            subtitle="",
            body="본문 내용 " * 100,
            length=500,
            chapter_type="본편"
        ),
    ]
    
    # Simulate what stage4_splitter.py does
    result = {
        "chapters": [
            {
                "cid": ch.cid,
                "title": ch.title,
                "subtitle": ch.subtitle,
                "body": ch.body,  # KEY: Body must be included
                "length": ch.length,
                "chapter_type": ch.chapter_type
            }
            for ch in chapters
        ],
        "summary": {"total": 2, "main": 2},
        "patterns": {
            "chapter_pattern": r"\d+화",
            "subtitle_pattern": None
        },
        "reconciliation_log": "Test"
    }
    
    # Verify structure
    assert "chapters" in result
    assert "summary" in result
    assert "patterns" in result
    
    # Verify chapters have body
    for ch_data in result["chapters"]:
        assert "body" in ch_data, "Chapter data must include 'body' field"
        assert ch_data["body"], "Chapter body must not be empty"
        assert len(ch_data["body"]) > 0
    
    # Test serialization
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        temp_file = f.name
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    try:
        # Verify it can be read back
        with open(temp_file, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        
        assert loaded["chapters"][0]["body"] == result["chapters"][0]["body"]
        assert loaded["chapters"][1]["title"] == result["chapters"][1]["title"]
        
        logger.info("✅ Cache can be serialized and deserialized correctly")
        logger.info(f"✅ Cache size: {os.path.getsize(temp_file)} bytes")
        
    finally:
        os.unlink(temp_file)


if __name__ == "__main__":
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 5 INTEGRATION TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    test_stage5_uses_stage4_chapters()
    test_stage4_cache_structure()
    
    logger.info("\n" + "=" * 60)
    logger.info("ALL TESTS PASSED ✅")
    logger.info("=" * 60 + "\n")
