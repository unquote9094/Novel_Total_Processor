"""Comprehensive demo showing boundary-based splitting vs pattern-based splitting"""

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


def demo_comparison():
    """Compare pattern-based vs boundary-based splitting"""
    
    # Create test file with 5 chapters
    test_content = """

프롤로그: 시작

프롤로그 내용입니다. """ + ("본문. " * 50) + """


1화 첫번째

첫 번째 챕터입니다. """ + ("본문. " * 50) + """


2화 두번째

두 번째 챕터입니다. """ + ("본문. " * 50) + """


3화 세번째

세 번째 챕터입니다. """ + ("본문. " * 50) + """


4화 네번째

네 번째 챕터입니다. """ + ("본문. " * 50)

    fd, test_file = tempfile.mkstemp(suffix='.txt')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        logger.info("=" * 80)
        logger.info("DEMO: Pattern-Based vs Boundary-Based Splitting")
        logger.info("=" * 80)
        
        splitter = Splitter()
        
        # Method 1: Pattern-based splitting (OLD WAY)
        logger.info("\n" + "=" * 80)
        logger.info("Method 1: Pattern-Based Splitting (OLD WAY)")
        logger.info("=" * 80)
        
        pattern = r'\d+화'
        logger.info(f"   → Using regex pattern: '{pattern}'")
        logger.info(f"   → May not match all chapters if titles vary")
        
        pattern_chapters = list(splitter.split(
            test_file,
            pattern,
            encoding='utf-8'
        ))
        
        logger.info(f"   → Result: {len(pattern_chapters)} chapters")
        for i, ch in enumerate(pattern_chapters):
            logger.info(f"      Chapter {i+1}: '{ch.title}' ({len(ch.body)} chars)")
        
        # Method 2: Boundary-based splitting (NEW WAY)
        logger.info("\n" + "=" * 80)
        logger.info("Method 2: Boundary-Based Splitting (NEW WAY)")
        logger.info("=" * 80)
        
        # Simulate boundaries from structural analyzer + optimizer
        boundaries = [
            {'line_num': 2, 'text': '프롤로그: 시작'},
            {'line_num': 7, 'text': '1화 첫번째'},
            {'line_num': 12, 'text': '2화 두번째'},
            {'line_num': 17, 'text': '3화 세번째'},
            {'line_num': 22, 'text': '4화 네번째'},
        ]
        
        logger.info(f"   → Using {len(boundaries)} pre-selected boundaries")
        logger.info(f"   → NO regex patterns involved")
        logger.info(f"   → Guaranteed exact count match")
        
        boundary_chapters = list(splitter.split_by_boundaries(
            test_file,
            boundaries,
            encoding='utf-8'
        ))
        
        logger.info(f"   → Result: {len(boundary_chapters)} chapters")
        for i, ch in enumerate(boundary_chapters):
            logger.info(f"      Chapter {i+1}: '{ch.title}' ({len(ch.body)} chars)")
        
        # Comparison
        logger.info("\n" + "=" * 80)
        logger.info("COMPARISON")
        logger.info("=" * 80)
        
        logger.info(f"   Pattern-based:  {len(pattern_chapters)} chapters")
        logger.info(f"   Boundary-based: {len(boundary_chapters)} chapters")
        logger.info(f"   Expected:       {len(boundaries)} chapters")
        
        if len(boundary_chapters) == len(boundaries):
            logger.info("\n   ✅ Boundary-based method returns EXACT count!")
        else:
            logger.info("\n   ❌ Boundary-based method count mismatch!")
        
        if len(pattern_chapters) == len(boundaries):
            logger.info("   ✅ Pattern-based method also got exact count (lucky!)")
        else:
            logger.info(f"   ⚠️  Pattern-based method missed {len(boundaries) - len(pattern_chapters)} chapters")
        
        logger.info("\n" + "=" * 80)
        logger.info("KEY ADVANTAGES OF BOUNDARY-BASED SPLITTING")
        logger.info("=" * 80)
        logger.info("   1. EXACT COUNT: Always returns len(boundaries) chapters")
        logger.info("   2. NO PATTERNS: Bypasses regex pattern matching entirely")
        logger.info("   3. FAST: Direct line-number based splitting")
        logger.info("   4. RELIABLE: Validates boundaries before splitting")
        logger.info("   5. FAIL-FAST: Clear errors for invalid boundaries")
        
    finally:
        os.unlink(test_file)


if __name__ == "__main__":
    demo_comparison()
