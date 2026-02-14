"""Test to reproduce the boundary conversion issue in Stage 5"""

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
from novel_total_processor.stages.topic_change_detector import TopicChangeDetector
from novel_total_processor.stages.splitter import Splitter
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


def test_full_pipeline():
    """Test the full pipeline from structural analysis to chapter splitting"""
    
    # Create test file
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
        
        # Stage 1-4: Generate and select boundaries
        logger.info("=" * 80)
        logger.info("Testing Full Pipeline: Stages 1-5")
        logger.info("=" * 80)
        
        client = MockGeminiClient()
        structural = StructuralAnalyzer()
        scorer = AIScorer(client)
        optimizer = GlobalOptimizer()
        splitter = Splitter()
        
        # Stage 1: Structural analysis
        logger.info("\n[Stage 1] Structural Analysis")
        candidates = structural.generate_candidates(
            test_file,
            encoding='utf-8',
            max_candidates=expected_count * 5
        )
        logger.info(f"  Generated {len(candidates)} candidates")
        for i, cand in enumerate(candidates[:10]):
            logger.info(f"    {i+1}. line_num={cand['line_num']}, text='{cand['text']}'")
        
        # Stage 2: AI Scoring (limited)
        logger.info("\n[Stage 2] AI Scoring")
        if len(candidates) <= 30:
            scored = scorer.score_candidates(test_file, candidates, encoding='utf-8', batch_size=5)
        else:
            scored = candidates
        logger.info(f"  Scored {len(scored)} candidates")
        
        # Stage 4: Global Optimization
        logger.info("\n[Stage 4] Global Optimization")
        selected = optimizer.select_optimal_boundaries(
            scored,
            expected_count,
            test_file,
            encoding='utf-8'
        )
        logger.info(f"  Selected {len(selected)}/{expected_count} boundaries")
        logger.info("  Selected boundaries:")
        for i, sel in enumerate(selected):
            logger.info(f"    {i+1}. line_num={sel['line_num']}, byte_pos={sel.get('byte_pos', 'N/A')}, text='{sel['text']}'")
        
        # Stage 5: Split using selected boundaries
        logger.info("\n[Stage 5] Splitting chapters using selected boundaries")
        
        # Extract title lines from selected candidates (THIS IS THE KEY PART)
        title_lines = [cand['text'] for cand in selected]
        logger.info(f"  Extracted {len(title_lines)} title_candidates:")
        for i, title in enumerate(title_lines):
            logger.info(f"    {i+1}. '{title}'")
        
        # Use splitter with permissive pattern
        permissive_pattern = r'.+'  # Match any non-empty line
        
        logger.info(f"  Calling splitter.split() with:")
        logger.info(f"    - pattern: {permissive_pattern}")
        logger.info(f"    - title_candidates: {len(title_lines)} items")
        
        chapters = list(splitter.split(
            test_file,
            permissive_pattern,
            subtitle_pattern=None,
            encoding='utf-8',
            title_candidates=title_lines
        ))
        
        logger.info(f"\n[Result] Created {len(chapters)} chapters from {len(selected)} selected boundaries")
        
        if len(chapters) == 0:
            logger.error("\n❌ ISSUE REPRODUCED: Got 0 chapters!")
            logger.error("  This is the bug we need to fix.")
            
            # Debug: Let's check if title_candidates match anything in the file
            logger.info("\n[Debug] Checking if title_candidates exist in file:")
            with open(test_file, 'r', encoding='utf-8') as f:
                file_lines = f.readlines()
            
            for i, title in enumerate(title_lines):
                logger.info(f"  Searching for: '{title}'")
                found = False
                for line_idx, line in enumerate(file_lines):
                    stripped = line.strip()
                    if stripped == title or title in stripped:
                        logger.info(f"    ✓ Found at line {line_idx}: '{stripped}'")
                        found = True
                        break
                if not found:
                    logger.error(f"    ✗ NOT FOUND in file")
        else:
            logger.info(f"✅ Success: Created {len(chapters)} chapters")
            for i, ch in enumerate(chapters):
                logger.info(f"  Chapter {i+1}: {ch.title} ({len(ch.body)} chars)")
        
    finally:
        os.unlink(test_file)


if __name__ == "__main__":
    test_full_pipeline()
