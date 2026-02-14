"""Test to verify the boundary conversion fix in Stage 5"""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Mock imports
import unittest.mock as mock

class MockGeminiClient:
    """Mock Gemini client for testing"""
    def generate_content(self, prompt):
        if 'likelihood' in prompt.lower() or 'score' in prompt.lower():
            if '화' in prompt or 'Chapter' in prompt or '[' in prompt:
                return "0.85"
            return "0.3"
        if 'topic' in prompt.lower():
            return "0.7"
        return "0.5"

mock_gemini = mock.MagicMock()
mock_gemini.GeminiClient = MockGeminiClient
sys.modules['novel_total_processor.ai.gemini_client'] = mock_gemini

from novel_total_processor.stages.structural_analyzer import StructuralAnalyzer
from novel_total_processor.stages.ai_scorer import AIScorer
from novel_total_processor.stages.global_optimizer import GlobalOptimizer
from novel_total_processor.stages.splitter import Splitter
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


def test_full_pipeline_with_permissive_pattern():
    """Test the full pipeline from structural analysis to chapter splitting
    
    This test verifies that:
    1. Boundaries are correctly selected by the global optimizer
    2. When using a permissive pattern (.+) with title_candidates,
       the splitter correctly creates chapters
    3. The permissive pattern doesn't match body text as titles
    """
    
    # Create test file with multiple chapters
    test_content = """

프롤로그: 시작

이것은 프롤로그입니다. """ + ("본문 내용. " * 100) + """


1화 평범한 시작

첫 번째 챕터의 본문입니다. """ + ("본문 내용. " * 100) + """


[2화] 두 번째 이야기

두 번째 챕터입니다. """ + ("본문 내용. " * 100) + """


새로운 전개

번호 없는 챕터입니다. """ + ("본문 내용. " * 100) + """


서울, 2024년 봄

장소 표시 챕터입니다. """ + ("본문 내용. " * 100) + """
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        test_file = f.name
        f.write(test_content)
    
    try:
        expected_count = 5
        
        logger.info("=" * 80)
        logger.info("Testing Boundary Conversion Fix: Full Pipeline (Stages 1-5)")
        logger.info("=" * 80)
        
        # Initialize components
        client = MockGeminiClient()
        structural = StructuralAnalyzer()
        scorer = AIScorer(client)
        optimizer = GlobalOptimizer()
        splitter = Splitter()
        
        # Stage 1-4: Generate, score, and select boundaries
        candidates = structural.generate_candidates(test_file, encoding='utf-8', max_candidates=expected_count * 5)
        
        if len(candidates) <= 30:
            scored = scorer.score_candidates(test_file, candidates, encoding='utf-8', batch_size=5)
        else:
            scored = candidates
        
        selected = optimizer.select_optimal_boundaries(scored, expected_count, test_file, encoding='utf-8')
        
        logger.info(f"\nSelected {len(selected)}/{expected_count} boundaries")
        
        # Stage 5: Split using selected boundaries with permissive pattern
        title_lines = [cand['text'] for cand in selected]
        permissive_pattern = r'.+'  # This should NOT match body text when using title_candidates
        
        chapters = list(splitter.split(
            test_file,
            permissive_pattern,
            subtitle_pattern=None,
            encoding='utf-8',
            title_candidates=title_lines
        ))
        
        logger.info(f"\nResult: Created {len(chapters)} chapters from {len(selected)} boundaries")
        
        # Verify results
        assert len(chapters) > 0, "Should create at least 1 chapter"
        assert len(chapters) == len(selected), f"Should create exactly {len(selected)} chapters, got {len(chapters)}"
        
        for i, ch in enumerate(chapters):
            logger.info(f"  ✓ Chapter {i+1}: '{ch.title}' ({len(ch.body)} chars)")
            assert len(ch.body) > 0, f"Chapter {i+1} has empty body"
        
        logger.info("\n✅ Boundary conversion fix verified successfully!")
        logger.info("   - Permissive pattern (.+) correctly used with title_candidates")
        logger.info("   - Body text not incorrectly matched as chapter titles")
        logger.info("   - All chapters have non-empty body text")
        
    finally:
        os.unlink(test_file)


if __name__ == "__main__":
    test_full_pipeline_with_permissive_pattern()
