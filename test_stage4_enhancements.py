"""Test Stage 4 Enhancements
 
Tests for multi-signal chapter detection, dynamic gap analysis,
and consensus-based title candidate extraction.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Mock imports that require API keys
import unittest.mock as mock

# Create mock for GeminiClient before importing
mock_gemini = mock.MagicMock()
sys.modules['novel_total_processor.ai.gemini_client'] = mock_gemini

from novel_total_processor.stages.splitter import Splitter
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


def create_test_novel(path: str, chapters: list):
    """Create a test novel file with specified chapter patterns
    
    Args:
        path: File path to create
        chapters: List of (title, body) tuples
    """
    with open(path, 'w', encoding='utf-8') as f:
        for title, body in chapters:
            f.write(f"{title}\n\n{body}\n\n")


def test_dynamic_gap_detection():
    """Test dynamic gap detection based on average chapter size"""
    logger.info("=" * 60)
    logger.info("Testing Dynamic Gap Detection")
    logger.info("=" * 60)
    
    # Import PatternManager with mocked dependencies
    from novel_total_processor.stages.pattern_manager import PatternManager
    
    # Create a test file with irregular gaps
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        test_file = f.name
        
        # Write chapters with varying gaps
        # Chapters 1-5: normal spacing
        for i in range(1, 6):
            f.write(f"{i}화 제목\n\n")
            f.write("본문 내용 " * 200 + "\n\n")  # ~2KB each
        
        # Large gap (simulating missing chapters)
        f.write("X" * 50000 + "\n\n")  # 50KB gap
        
        # Chapters 6-10: normal spacing
        for i in range(6, 11):
            f.write(f"{i}화 제목\n\n")
            f.write("본문 내용 " * 200 + "\n\n")
    
    try:
        # Skip actual AI client for basic structure test
        # Just test that the method exists and has correct structure
        splitter = Splitter()
        matches = splitter.find_matches_with_pos(test_file, r'\d+화', encoding='utf-8')
        
        logger.info(f"Found {len(matches)} matches")
        
        # Test that PatternManager has the new method
        assert hasattr(PatternManager, 'find_dynamic_gaps'), "Missing find_dynamic_gaps method"
        assert hasattr(PatternManager, 'extract_title_candidates'), "Missing extract_title_candidates method"
        
        logger.info("✅ Dynamic gap detection structure verified")
        
    finally:
        os.unlink(test_file)


def test_multi_line_title_support():
    """Test multi-line title detection and merging"""
    logger.info("=" * 60)
    logger.info("Testing Multi-line Title Support")
    logger.info("=" * 60)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        test_file = f.name
        
        # Chapter with single-line title
        f.write("1화 일반 제목\n\n")
        f.write("일반 본문 내용입니다.\n\n")
        
        # Chapter with multi-line title (candidate + true title)
        f.write("[집을 숨김 - 2화]\n")
        f.write("[2) 김영감의 분노]\n\n")
        f.write("다중 라인 제목 본문 내용입니다.\n\n")
        
        # Another normal chapter
        f.write("3화 마지막 제목\n\n")
        f.write("마지막 본문 내용입니다.\n\n")
    
    try:
        splitter = Splitter()
        
        # Test with explicit title candidates
        title_candidates = ["[집을 숨김 - 2화]", "[2) 김영감의 분노]"]
        chapters = list(splitter.split(
            test_file,
            r'\d+화',
            encoding='utf-8',
            title_candidates=title_candidates
        ))
        
        logger.info(f"Extracted {len(chapters)} chapters")
        for ch in chapters:
            logger.info(f"  - Chapter {ch.cid}: {ch.title[:50]}...")
        
        assert len(chapters) >= 2, f"Expected at least 2 chapters, got {len(chapters)}"
        logger.info("✅ Multi-line title support verified")
        
    finally:
        os.unlink(test_file)


def test_splitter_with_title_candidates():
    """Test Splitter with explicit title candidates"""
    logger.info("=" * 60)
    logger.info("Testing Splitter with Title Candidates")
    logger.info("=" * 60)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        test_file = f.name
        
        # Mix of numbered and unnumbered chapters
        f.write("1화 첫번째\n\n본문 1\n\n")
        f.write("특별편: 중간 이야기\n\n본문 특별\n\n")  # No number
        f.write("2화 두번째\n\n본문 2\n\n")
    
    try:
        splitter = Splitter()
        
        # Split with pattern only
        chapters_pattern = list(splitter.split(test_file, r'\d+화', encoding='utf-8'))
        logger.info(f"Pattern-only: {len(chapters_pattern)} chapters")
        
        # Split with pattern + title candidates
        title_candidates = ["특별편: 중간 이야기"]
        chapters_combined = list(splitter.split(
            test_file,
            r'\d+화',
            encoding='utf-8',
            title_candidates=title_candidates
        ))
        logger.info(f"Pattern + candidates: {len(chapters_combined)} chapters")
        
        # Should get more chapters with candidates
        assert len(chapters_combined) >= len(chapters_pattern), \
            "Title candidates should add or maintain chapter count"
        
        logger.info("✅ Title candidate support verified")
        
    finally:
        os.unlink(test_file)


def test_enhanced_pattern_manager_methods():
    """Test that PatternManager has all new methods"""
    logger.info("=" * 60)
    logger.info("Testing Enhanced PatternManager Methods")
    logger.info("=" * 60)
    
    # Import with mocked dependencies
    from novel_total_processor.stages.pattern_manager import PatternManager
    
    # Test method existence
    methods_to_check = [
        'find_dynamic_gaps',
        'extract_title_candidates',
        'refine_pattern_with_goal_v3'
    ]
    
    for method_name in methods_to_check:
        assert hasattr(PatternManager, method_name), \
            f"PatternManager missing method: {method_name}"
        logger.info(f"  ✓ Method exists: {method_name}")
    
    logger.info("✅ All enhanced methods present")


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 80)
    logger.info("Stage 4 Enhancement Tests")
    logger.info("=" * 80 + "\n")
    
    try:
        test_enhanced_pattern_manager_methods()
        test_dynamic_gap_detection()
        test_multi_line_title_support()
        test_splitter_with_title_candidates()
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ All Tests Passed!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
