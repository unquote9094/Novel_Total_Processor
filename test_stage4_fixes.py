"""Test Stage 4 Enhancement Fixes

Tests for:
1. AI response null handling
2. Regex validation and sanitization
3. Stagnation detection and automatic escalation
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
class MockGeminiClient:
    """Mock Gemini client for testing AI behavior without requiring API keys.
    
    This mock allows testing of AI-dependent code paths without making actual API calls.
    
    Args:
        return_value: The value to return from generate_content(). Can be None, empty string,
                     or any valid response string. Defaults to None.
        raise_error: If True, generate_content() will raise an Exception. Used to test
                    error handling. Defaults to False.
    """
    
    def __init__(self, return_value=None, raise_error=False):
        self.return_value = return_value
        self.raise_error = raise_error
        self.call_count = 0
    
    def generate_content(self, prompt):
        """Mock generate_content method.
        
        Args:
            prompt: The prompt to generate content for (ignored in mock)
            
        Returns:
            The configured return_value
            
        Raises:
            Exception: If raise_error is True
        """
        self.call_count += 1
        
        if self.raise_error:
            raise Exception("Mock AI error")
        
        return self.return_value

mock_gemini_module = mock.MagicMock()
mock_gemini_module.GeminiClient = MockGeminiClient
sys.modules['novel_total_processor.ai.gemini_client'] = mock_gemini_module

from novel_total_processor.stages.pattern_manager import PatternManager
from novel_total_processor.stages.ai_scorer import AIScorer
from novel_total_processor.stages.topic_change_detector import TopicChangeDetector
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


def test_ai_response_null_handling():
    """Test that None/empty AI responses don't cause crashes"""
    logger.info("=" * 60)
    logger.info("Testing AI Response Null Handling")
    logger.info("=" * 60)
    
    # Test 1: None response in PatternManager
    logger.info("  Testing PatternManager with None response...")
    mock_client = MockGeminiClient(return_value=None)
    pm = PatternManager(mock_client)
    result = pm._generate_regex_from_ai("test prompt")
    assert result is None, "Expected None result for None AI response"
    logger.info("    ✓ PatternManager handles None response correctly")
    
    # Test 2: Empty string response in PatternManager
    logger.info("  Testing PatternManager with empty response...")
    mock_client = MockGeminiClient(return_value="")
    pm = PatternManager(mock_client)
    result = pm._generate_regex_from_ai("test prompt")
    assert result is None, "Expected None result for empty AI response"
    logger.info("    ✓ PatternManager handles empty response correctly")
    
    # Test 3: None response in AIScorer
    logger.info("  Testing AIScorer with None response...")
    mock_client = MockGeminiClient(return_value=None)
    scorer = AIScorer(mock_client)
    
    # Test with simple context
    context = {'before': '본문 내용', 'after': '본문 내용'}
    score = scorer._score_single_candidate('1화 테스트', context)
    assert score == 0.5, f"Expected default score 0.5 for None response, got {score}"
    logger.info("    ✓ AIScorer handles None response with default score")
    
    # Test 4: None response in TopicChangeDetector
    logger.info("  Testing TopicChangeDetector with None response...")
    mock_client = MockGeminiClient(return_value=None)
    detector = TopicChangeDetector(mock_client)
    score = detector._detect_topic_change("text1", "text2")
    assert score == 0.5, f"Expected default score 0.5 for None response, got {score}"
    logger.info("    ✓ TopicChangeDetector handles None response with default score")
    
    logger.info("✅ All null handling tests passed")


def test_regex_validation():
    """Test regex validation and sanitization"""
    logger.info("=" * 60)
    logger.info("Testing Regex Validation")
    logger.info("=" * 60)
    
    # Test 1: Reject leading '?'
    logger.info("  Testing rejection of leading '?'...")
    mock_client = MockGeminiClient(return_value="?.*화")
    pm = PatternManager(mock_client)
    result = pm._generate_regex_from_ai("test prompt")
    assert result is None, "Expected None for pattern starting with '?'"
    logger.info("    ✓ Leading '?' pattern rejected")
    
    # Test 2: Reject unclosed named group (mismatched parentheses)
    logger.info("  Testing rejection of mismatched parentheses...")
    mock_client = MockGeminiClient(return_value="(?P<chapter>\\d+")
    pm = PatternManager(mock_client)
    result = pm._generate_regex_from_ai("test prompt")
    assert result is None, "Expected None for mismatched parentheses"
    logger.info("    ✓ Mismatched parentheses rejected")
    
    # Test 3: Accept valid regex
    logger.info("  Testing acceptance of valid regex...")
    mock_client = MockGeminiClient(return_value="\\d+화")
    pm = PatternManager(mock_client)
    result = pm._generate_regex_from_ai("test prompt")
    assert result == "\\d+화", f"Expected '\\d+화', got {result}"
    logger.info("    ✓ Valid regex accepted")
    
    # Test 4: Reject invalid regex
    logger.info("  Testing rejection of invalid regex...")
    mock_client = MockGeminiClient(return_value="[invalid")
    pm = PatternManager(mock_client)
    result = pm._generate_regex_from_ai("test prompt")
    assert result is None, "Expected None for invalid regex"
    logger.info("    ✓ Invalid regex rejected")
    
    logger.info("✅ All regex validation tests passed")


def test_stagnation_detection():
    """Test stagnation detection logic"""
    logger.info("=" * 60)
    logger.info("Testing Stagnation Detection")
    logger.info("=" * 60)
    
    # Import ChapterSplitRunner to test the helper method
    # We need to mock the database first
    import unittest.mock as mock
    mock_db = mock.MagicMock()
    
    # Mock the Database class
    sys.modules['novel_total_processor.db.schema'] = mock.MagicMock()
    from novel_total_processor.stages.stage4_splitter import ChapterSplitRunner
    
    runner = ChapterSplitRunner(mock_db)
    
    # Test 1: No stagnation (counts change)
    logger.info("  Testing non-stagnant case (changing counts)...")
    chapter_count_history = [10, 11, 12]
    is_stagnant = runner._is_stagnant(chapter_count_history, threshold=3)
    assert not is_stagnant, "Expected no stagnation for changing counts"
    logger.info("    ✓ No stagnation detected for changing counts")
    
    # Test 2: Stagnation detected (same count)
    logger.info("  Testing stagnant case (same count 3 times)...")
    chapter_count_history = [10, 10, 10]
    is_stagnant = runner._is_stagnant(chapter_count_history, threshold=3)
    assert is_stagnant, "Expected stagnation for same counts"
    logger.info("    ✓ Stagnation detected for repeated counts")
    
    # Test 3: Stagnation after initial change
    logger.info("  Testing stagnation after initial changes...")
    chapter_count_history = [8, 10, 10, 10, 10]
    is_stagnant = runner._is_stagnant(chapter_count_history, threshold=3)
    assert is_stagnant, "Expected stagnation for last 3 same counts"
    logger.info("    ✓ Stagnation detected after initial improvement")
    
    # Test 4: Not enough history
    logger.info("  Testing insufficient history...")
    chapter_count_history = [10, 10]
    is_stagnant = runner._is_stagnant(chapter_count_history, threshold=3)
    assert not is_stagnant, "Expected no stagnation with insufficient history"
    logger.info("    ✓ No stagnation with insufficient history")
    
    logger.info("✅ All stagnation detection tests passed")


def test_advanced_pipeline_components():
    """Test that advanced pipeline components exist"""
    logger.info("=" * 60)
    logger.info("Testing Advanced Pipeline Components")
    logger.info("=" * 60)
    
    # Import components
    from novel_total_processor.stages.structural_analyzer import StructuralAnalyzer
    from novel_total_processor.stages.global_optimizer import GlobalOptimizer
    
    # Test that classes exist and can be instantiated
    logger.info("  Testing StructuralAnalyzer...")
    analyzer = StructuralAnalyzer()
    assert hasattr(analyzer, 'generate_candidates'), "Missing generate_candidates method"
    logger.info("    ✓ StructuralAnalyzer instantiated")
    
    logger.info("  Testing AIScorer...")
    mock_client = MockGeminiClient(return_value="0.5")
    scorer = AIScorer(mock_client)
    assert hasattr(scorer, 'score_candidates'), "Missing score_candidates method"
    logger.info("    ✓ AIScorer instantiated")
    
    logger.info("  Testing GlobalOptimizer...")
    optimizer = GlobalOptimizer()
    assert hasattr(optimizer, 'select_optimal_boundaries'), "Missing select_optimal_boundaries method"
    logger.info("    ✓ GlobalOptimizer instantiated")
    
    logger.info("  Testing TopicChangeDetector...")
    detector = TopicChangeDetector(mock_client)
    assert hasattr(detector, 'detect_topic_boundaries'), "Missing detect_topic_boundaries method"
    logger.info("    ✓ TopicChangeDetector instantiated")
    
    logger.info("✅ All advanced pipeline components present")


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 80)
    logger.info("Stage 4 Enhancement Fixes Tests")
    logger.info("=" * 80 + "\n")
    
    try:
        test_ai_response_null_handling()
        test_regex_validation()
        test_stagnation_detection()
        test_advanced_pipeline_components()
        
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
