"""Comprehensive tests for Stage 4 advanced escalation components

Tests for:
- StructuralAnalyzer: transition point detection
- AIScorer: likelihood scoring
- GlobalOptimizer: boundary selection
- TopicChangeDetector: semantic boundaries
- Full escalation pipeline integration
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

from novel_total_processor.stages.structural_analyzer import StructuralAnalyzer
from novel_total_processor.stages.global_optimizer import GlobalOptimizer
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


def create_test_novel_irregular(path: str):
    """Create a test novel with irregular chapter markers
    
    Simulates a difficult novel with:
    - Varied chapter title formats
    - Some chapters without numbers
    - Mixed patterns
    - Structural cues only
    """
    with open(path, 'w', encoding='utf-8') as f:
        # Chapter 1: Standard format
        f.write("1화 평범한 시작\n\n")
        f.write("이것은 첫 번째 챕터의 본문입니다. " * 50 + "\n\n")
        
        # Chapter 2: No number, short line after blank
        f.write("\n\n")
        f.write("새로운 시작\n\n")
        f.write("이것은 두 번째 챕터입니다. " * 50 + "\n\n")
        
        # Chapter 3: Bracketed format
        f.write("\n\n")
        f.write("[특별편 - 회상]\n\n")
        f.write("회상 장면의 본문입니다. " * 50 + "\n\n")
        
        # Chapter 4: Place marker
        f.write("\n\n")
        f.write("서울, 2024년\n\n")
        f.write("장소와 시간 표시 후 본문. " * 50 + "\n\n")
        
        # Chapter 5: Separator style
        f.write("\n\n")
        f.write("***\n\n")
        f.write("구분선 후 새 챕터. " * 50 + "\n\n")


def test_structural_analyzer():
    """Test StructuralAnalyzer candidate generation"""
    logger.info("=" * 60)
    logger.info("Testing StructuralAnalyzer")
    logger.info("=" * 60)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        test_file = f.name
        create_test_novel_irregular(test_file)
    
    try:
        analyzer = StructuralAnalyzer()
        
        # Generate candidates
        candidates = analyzer.generate_candidates(
            test_file,
            encoding='utf-8',
            max_candidates=100
        )
        
        logger.info(f"Generated {len(candidates)} candidates")
        
        # Should find multiple candidates (at least a few)
        assert len(candidates) > 0, "No candidates found"
        
        # Check candidate structure
        for i, cand in enumerate(candidates[:5]):
            logger.info(f"  Candidate {i+1}:")
            logger.info(f"    Line: {cand['text'][:50]}")
            logger.info(f"    Confidence: {cand['confidence']:.2f}")
            logger.info(f"    Features: {list(cand['features'].keys())}")
            
            # Verify required fields
            assert 'line_num' in cand
            assert 'text' in cand
            assert 'confidence' in cand
            assert 'features' in cand
            assert 0.0 <= cand['confidence'] <= 1.0
        
        logger.info("✅ StructuralAnalyzer test passed")
        
    finally:
        os.unlink(test_file)


def test_global_optimizer():
    """Test GlobalOptimizer boundary selection"""
    logger.info("=" * 60)
    logger.info("Testing GlobalOptimizer")
    logger.info("=" * 60)
    
    # Create test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        test_file = f.name
        
        # Write chapters with known positions
        for i in range(10):
            f.write(f"\n\n{i+1}화 제목\n\n")
            f.write("본문 내용 " * 100 + "\n\n")
    
    try:
        # Create mock candidates (more than we need)
        candidates = []
        for i in range(20):
            candidates.append({
                'line_num': i * 5,
                'text': f"후보 {i+1}",
                'confidence': 0.5 + (i % 5) * 0.1,  # Varying confidence
                'ai_score': 0.6 + (i % 4) * 0.1,
                'byte_pos': i * 1000
            })
        
        optimizer = GlobalOptimizer()
        
        # Select exactly 10 boundaries
        expected_count = 10
        selected = optimizer.select_optimal_boundaries(
            candidates,
            expected_count,
            test_file,
            encoding='utf-8'
        )
        
        logger.info(f"Selected {len(selected)}/{expected_count} boundaries")
        
        # Verify selection
        assert len(selected) <= expected_count, f"Selected too many: {len(selected)}"
        
        # Check that selected candidates have combined scores
        for sel in selected:
            assert 'combined_score' in sel
            logger.info(f"  Selected: line {sel['line_num']}, score {sel['combined_score']:.2f}")
        
        # Verify they're sorted by position
        positions = [s['byte_pos'] for s in selected]
        assert positions == sorted(positions), "Selected boundaries not sorted by position"
        
        logger.info("✅ GlobalOptimizer test passed")
        
    finally:
        os.unlink(test_file)


def test_ai_scorer():
    """Test AIScorer with mocked AI client"""
    logger.info("=" * 60)
    logger.info("Testing AIScorer (with mocked AI)")
    logger.info("=" * 60)
    
    from novel_total_processor.stages.ai_scorer import AIScorer
    
    # Create test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        test_file = f.name
        
        f.write("이전 본문입니다.\n")
        f.write("1화 챕터 제목\n")
        f.write("챕터 본문입니다.\n")
    
    try:
        # Mock AI client
        mock_client = mock.MagicMock()
        mock_client.generate_content.return_value = "0.8"  # Mock score
        
        scorer = AIScorer(mock_client)
        
        # Create test candidates
        candidates = [
            {
                'line_num': 1,
                'text': '1화 챕터 제목',
                'confidence': 0.7
            }
        ]
        
        # Score candidates
        scored = scorer.score_candidates(
            test_file,
            candidates,
            encoding='utf-8',
            batch_size=1
        )
        
        logger.info(f"Scored {len(scored)} candidates")
        
        # Verify scoring
        assert len(scored) == 1
        assert 'ai_score' in scored[0]
        logger.info(f"  AI Score: {scored[0]['ai_score']}")
        
        # Verify AI was called
        assert mock_client.generate_content.called
        
        logger.info("✅ AIScorer test passed")
        
    finally:
        os.unlink(test_file)


def test_topic_change_detector():
    """Test TopicChangeDetector with mocked AI"""
    logger.info("=" * 60)
    logger.info("Testing TopicChangeDetector (with mocked AI)")
    logger.info("=" * 60)
    
    from novel_total_processor.stages.topic_change_detector import TopicChangeDetector
    
    # Create test file with clear topic changes
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        test_file = f.name
        
        # Topic 1: School
        f.write("학교에서의 하루. " * 100 + "\n\n")
        
        # Topic 2: Home (clear change)
        f.write("집에 돌아온 주인공. " * 100 + "\n\n")
        
        # Topic 3: Adventure (another change)
        f.write("새로운 모험이 시작되었다. " * 100 + "\n\n")
    
    try:
        # Mock AI client to return high change scores
        mock_client = mock.MagicMock()
        mock_client.generate_content.return_value = "0.8"
        
        detector = TopicChangeDetector(mock_client)
        
        # Detect boundaries
        candidates = detector.detect_topic_boundaries(
            test_file,
            expected_count=3,
            encoding='utf-8'
        )
        
        logger.info(f"Detected {len(candidates)} topic-change boundaries")
        
        # Should find some candidates
        for cand in candidates:
            logger.info(f"  Topic change at line {cand['line_num']}: {cand['text'][:30]}")
            assert 'source' in cand
            assert cand['source'] == 'topic_change'
        
        logger.info("✅ TopicChangeDetector test passed")
        
    finally:
        os.unlink(test_file)


def test_escalation_integration():
    """Test that all components work together"""
    logger.info("=" * 60)
    logger.info("Testing Escalation Pipeline Integration")
    logger.info("=" * 60)
    
    # Verify all components can be imported and instantiated
    from novel_total_processor.stages.structural_analyzer import StructuralAnalyzer
    from novel_total_processor.stages.ai_scorer import AIScorer
    from novel_total_processor.stages.global_optimizer import GlobalOptimizer
    from novel_total_processor.stages.topic_change_detector import TopicChangeDetector
    
    mock_client = mock.MagicMock()
    
    # Instantiate all components
    structural = StructuralAnalyzer()
    scorer = AIScorer(mock_client)
    optimizer = GlobalOptimizer()
    detector = TopicChangeDetector(mock_client)
    
    logger.info("✅ All components instantiated successfully")
    
    # Verify they have expected methods
    assert hasattr(structural, 'generate_candidates')
    assert hasattr(scorer, 'score_candidates')
    assert hasattr(optimizer, 'select_optimal_boundaries')
    assert hasattr(detector, 'detect_topic_boundaries')
    
    logger.info("✅ All expected methods present")
    logger.info("✅ Integration test passed")


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 80)
    logger.info("Stage 4 Advanced Escalation Tests")
    logger.info("=" * 80 + "\n")
    
    try:
        test_structural_analyzer()
        test_global_optimizer()
        test_ai_scorer()
        test_topic_change_detector()
        test_escalation_integration()
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ All Advanced Escalation Tests Passed!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
