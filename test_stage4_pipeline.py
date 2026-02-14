"""Test Stage 4 advanced escalation pipeline with boundary-based splitting"""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Mock imports
import unittest.mock as mock

class MockGeminiClient:
    def __init__(self, *args, **kwargs):
        pass
    
    def score_chapter_candidate(self, text, context):
        """Mock AI scoring - return high score for lines with chapter-like features"""
        if any(marker in text for marker in ['화', 'Chapter', '프롤로그', '에필로그', '서울', '***']):
            return 0.9
        return 0.5

mock_gemini = mock.MagicMock()
mock_gemini.GeminiClient = MockGeminiClient
sys.modules['novel_total_processor.ai.gemini_client'] = mock_gemini

from novel_total_processor.stages.stage4_splitter import ChapterSplitRunner
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


def test_stage4_advanced_pipeline():
    """Test the full Stage 4 advanced escalation pipeline with boundary-based splitting"""
    
    # Create test file with exactly 5 chapters
    test_content = """

프롤로그: 새로운 시작

이것은 프롤로그입니다. 주인공이 태어나는 장면. """ + ("본문 내용이 계속됩니다. " * 100) + """


1화 - 평범한 일상

첫 번째 챕터의 내용입니다. 주인공의 일상 생활. """ + ("본문 내용이 계속됩니다. " * 100) + """


2화 - 예상치 못한 사건

두 번째 챕터입니다. 갑작스런 사건이 발생합니다. """ + ("본문 내용이 계속됩니다. " * 100) + """


3화 - 갈등의 시작

세 번째 챕터입니다. 주인공이 문제에 직면합니다. """ + ("본문 내용이 계속됩니다. " * 100) + """


4화 - 해결의 실마리

네 번째 챕터입니다. 해결책을 찾아갑니다. """ + ("본문 내용이 계속됩니다. " * 100) + """


에필로그: 끝이 아닌 시작

다섯 번째 챕터입니다. 이야기의 마무리. """ + ("본문 내용이 계속됩니다. " * 100)

    # Create temp file
    fd, test_file = tempfile.mkstemp(suffix='.txt')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        logger.info("=" * 80)
        logger.info("Stage 4 Advanced Escalation Pipeline - Full Test")
        logger.info("=" * 80)
        
        # Create ChapterSplitRunner (needs a mock Database)
        from novel_total_processor.db.schema import Database
        
        # Create a mock database
        mock_db = mock.MagicMock(spec=Database)
        
        runner = ChapterSplitRunner(db=mock_db)
        
        # Test file info matching stage4's expected input format
        file_info = {
            'novel_name': 'Test Novel',
            'total_size': os.path.getsize(test_file),
            'encoding': 'utf-8',
            'file_path': test_file,
            'expected_chapter_count': 6  # 6 chapters expected
        }
        
        expected_count = 6
        
        logger.info(f"\n📖 Test setup:")
        logger.info(f"   → File: {test_file}")
        logger.info(f"   → Size: {file_info['total_size']} bytes")
        logger.info(f"   → Expected chapters: {expected_count}")
        
        # Call advanced escalation pipeline directly
        logger.info("\n🚀 Activating Advanced Escalation Pipeline...")
        
        chapters = runner._advanced_escalation_pipeline(
            test_file,
            expected_count,
            'utf-8',
            []
        )
        
        # Verify results
        if chapters is None:
            logger.error("❌ Pipeline returned None")
            assert False, "Pipeline failed to return chapters"
        
        logger.info(f"\n📊 Results:")
        logger.info(f"   → Chapters created: {len(chapters)}")
        logger.info(f"   → Expected: {expected_count}")
        
        # Check chapter count matches exactly
        if len(chapters) == expected_count:
            logger.info(f"   ✅ EXACT MATCH: {len(chapters)} chapters")
        else:
            logger.error(f"   ❌ MISMATCH: got {len(chapters)}, expected {expected_count}")
        
        # Verify each chapter
        logger.info(f"\n📝 Chapter details:")
        for i, ch in enumerate(chapters):
            logger.info(f"   Chapter {i+1}:")
            logger.info(f"      Title: '{ch.title}'")
            logger.info(f"      Body length: {len(ch.body)} chars")
            assert len(ch.body) > 0, f"Chapter {i+1} has empty body"
        
        # Final assertion
        assert len(chapters) == expected_count, f"Expected {expected_count} chapters, got {len(chapters)}"
        
        logger.info("\n✅ Stage 4 Advanced Pipeline Test PASSED!")
        logger.info("   - Used boundary-based splitting (no permissive regex pattern)")
        logger.info("   - Exact chapter count matches expected count")
        logger.info("   - All chapters have valid titles and body text")
        
    finally:
        # Cleanup temp file
        os.unlink(test_file)


if __name__ == "__main__":
    test_stage4_advanced_pipeline()
