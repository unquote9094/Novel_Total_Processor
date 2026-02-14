"""Test for direct boundary-based splitting in Stage 4 advanced pipeline"""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Mock imports
import unittest.mock as mock

class MockGeminiClient:
    pass

mock_gemini = mock.MagicMock()
mock_gemini.GeminiClient = MockGeminiClient
sys.modules['novel_total_processor.ai.gemini_client'] = mock_gemini

from novel_total_processor.stages.splitter import Splitter
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


def test_split_by_boundaries():
    """Test the new split_by_boundaries method that bypasses regex patterns"""
    
    # Create test file with multiple chapters
    test_content = """

프롤로그: 시작

이것은 프롤로그입니다. """ + ("본문 내용. " * 100) + """


1화 평범한 시작

첫 번째 챕터의 본문입니다. """ + ("본문 내용. " * 100) + """


[2화] 두 번째 이야기

두 번째 챕터입니다. """ + ("본문 내용. " * 100) + """


새로운 전개

세 번째 챕터입니다. """ + ("본문 내용. " * 100) + """


서울, 2024년 봄

네 번째 챕터입니다. """ + ("본문 내용. " * 100)

    # Create temp file
    fd, test_file = tempfile.mkstemp(suffix='.txt')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        logger.info("=" * 80)
        logger.info("Testing Direct Boundary-Based Splitting (No Regex Patterns)")
        logger.info("=" * 80)
        
        # Create splitter
        splitter = Splitter()
        
        # Define boundaries directly (simulating what global optimizer would return)
        boundaries = [
            {'line_num': 2, 'text': '프롤로그: 시작', 'byte_pos': 2},
            {'line_num': 7, 'text': '1화 평범한 시작', 'byte_pos': 1560},
            {'line_num': 12, 'text': '[2화] 두 번째 이야기', 'byte_pos': 3124},
            {'line_num': 17, 'text': '새로운 전개', 'byte_pos': 4684},
            {'line_num': 22, 'text': '서울, 2024년 봄', 'byte_pos': 6242},
        ]
        
        expected_count = len(boundaries)
        logger.info(f"\nBoundary count: {len(boundaries)} (expected: {expected_count})")
        logger.info(f"Boundary format: line_num={boundaries[0]['line_num']}, text='{boundaries[0]['text']}'")
        
        # Split using boundaries directly (no regex pattern!)
        logger.info("\n🚀 Calling split_by_boundaries() - NO REGEX PATTERNS USED")
        chapters = list(splitter.split_by_boundaries(
            test_file,
            boundaries,
            encoding='utf-8'
        ))
        
        logger.info(f"\nResult: Created {len(chapters)} chapters from {len(boundaries)} boundaries")
        
        # Verify results
        assert len(chapters) == expected_count, f"Expected {expected_count} chapters, got {len(chapters)}"
        
        for i, ch in enumerate(chapters):
            logger.info(f"  ✓ Chapter {i+1}: '{ch.title}' ({len(ch.body)} chars)")
            assert len(ch.body) > 0, f"Chapter {i+1} has empty body"
            assert ch.title == boundaries[i]['text'], f"Chapter {i+1} title mismatch"
        
        logger.info("\n✅ Boundary-based splitting verified successfully!")
        logger.info("   - NO regex patterns used")
        logger.info("   - Split directly using line numbers from boundaries")
        logger.info("   - Exact chapter count matches boundary count")
        logger.info("   - All chapters have non-empty body text")
        
    finally:
        # Cleanup temp file
        os.unlink(test_file)


def test_boundary_validation():
    """Test that invalid boundaries are properly rejected"""
    
    test_content = """Line 0
Line 1
Line 2
Line 3
Line 4"""

    fd, test_file = tempfile.mkstemp(suffix='.txt')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        logger.info("\n" + "=" * 80)
        logger.info("Testing Boundary Validation")
        logger.info("=" * 80)
        
        splitter = Splitter()
        
        # Test 1: Empty boundaries should raise error
        logger.info("\n📋 Test 1: Empty boundaries list")
        try:
            list(splitter.split_by_boundaries(test_file, [], encoding='utf-8'))
            assert False, "Should have raised ValueError for empty boundaries"
        except ValueError as e:
            logger.info(f"   ✓ Correctly rejected: {e}")
        
        # Test 2: Boundary missing line_num
        logger.info("\n📋 Test 2: Boundary missing line_num")
        try:
            invalid_boundaries = [{'text': 'Title', 'byte_pos': 0}]
            list(splitter.split_by_boundaries(test_file, invalid_boundaries, encoding='utf-8'))
            assert False, "Should have raised ValueError for missing line_num"
        except ValueError as e:
            logger.info(f"   ✓ Correctly rejected: {e}")
        
        # Test 3: Boundary with empty text
        logger.info("\n📋 Test 3: Boundary with empty text")
        try:
            invalid_boundaries = [{'line_num': 1, 'text': '   '}]
            list(splitter.split_by_boundaries(test_file, invalid_boundaries, encoding='utf-8'))
            assert False, "Should have raised ValueError for empty text"
        except ValueError as e:
            logger.info(f"   ✓ Correctly rejected: {e}")
        
        # Test 4: Boundary with out-of-range line number
        logger.info("\n📋 Test 4: Boundary with out-of-range line number")
        try:
            invalid_boundaries = [{'line_num': 999, 'text': 'Title'}]
            list(splitter.split_by_boundaries(test_file, invalid_boundaries, encoding='utf-8'))
            assert False, "Should have raised ValueError for out-of-range line_num"
        except ValueError as e:
            logger.info(f"   ✓ Correctly rejected: {e}")
        
        logger.info("\n✅ All validation tests passed!")
        logger.info("   - Invalid boundaries are rejected")
        logger.info("   - Clear error messages provided")
        
    finally:
        os.unlink(test_file)


if __name__ == "__main__":
    test_split_by_boundaries()
    test_boundary_validation()
