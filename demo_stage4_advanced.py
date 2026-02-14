"""Demo script for Stage 4 advanced escalation features

Demonstrates the full escalation pipeline with a difficult test case.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Mock imports that require API keys for demo
import unittest.mock as mock

# Create mock for GeminiClient
mock_gemini_module = mock.MagicMock()

class MockGeminiClient:
    """Mock Gemini client for demo"""
    
    def generate_content(self, prompt):
        """Mock AI responses based on prompt type"""
        # For scoring prompts, return a score
        if 'likelihood' in prompt.lower() or 'score' in prompt.lower():
            # Analyze the prompt to give sensible scores
            if '화' in prompt or 'Chapter' in prompt or '[' in prompt:
                return "0.85"  # High score for chapter-like lines
            else:
                return "0.3"   # Low score for body text
        
        # For topic change detection
        if 'topic' in prompt.lower() or 'scene' in prompt.lower():
            return "0.7"  # Moderate topic change
        
        # Default
        return "0.5"

mock_gemini_module.GeminiClient = MockGeminiClient
sys.modules['novel_total_processor.ai.gemini_client'] = mock_gemini_module

from novel_total_processor.stages.structural_analyzer import StructuralAnalyzer
from novel_total_processor.stages.ai_scorer import AIScorer
from novel_total_processor.stages.global_optimizer import GlobalOptimizer
from novel_total_processor.stages.topic_change_detector import TopicChangeDetector
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


def create_difficult_novel(path: str, num_chapters: int = 10):
    """Create a novel with highly irregular chapter patterns
    
    Simulates a real-world difficult case:
    - Mixed numbering systems
    - Some chapters without numbers
    - Various separator styles
    - Inconsistent formatting
    - Realistic body text lengths
    """
    with open(path, 'w', encoding='utf-8') as f:
        # Prologue - no number
        f.write("\n\n")
        f.write("프롤로그: 시작\n\n")
        f.write("이것은 프롤로그입니다. " * 100 + "\n\n")
        
        # Chapter 1: Standard Korean
        f.write("\n\n")
        f.write("1화 평범한 시작\n\n")
        f.write("첫 번째 챕터의 본문입니다. " * 120 + "\n\n")
        
        # Chapter 2: Bracketed
        f.write("\n\n")
        f.write("[2화] 두 번째 이야기\n\n")
        f.write("두 번째 챕터입니다. " * 120 + "\n\n")
        
        # Chapter 3: No number, just title
        f.write("\n\n")
        f.write("새로운 전개\n\n")
        f.write("번호 없는 챕터입니다. " * 120 + "\n\n")
        
        # Chapter 4: Time/place marker
        f.write("\n\n")
        f.write("서울, 2024년 봄\n\n")
        f.write("장소 표시 챕터입니다. " * 120 + "\n\n")
        
        # Chapter 5: English style
        f.write("\n\n")
        f.write("Chapter 5: The Discovery\n\n")
        f.write("영문 스타일 챕터입니다. " * 120 + "\n\n")
        
        # Chapter 6: Separator style
        f.write("\n\n")
        f.write("***\n\n")
        f.write("구분선 스타일 챕터입니다. " * 120 + "\n\n")
        
        # Chapter 7: Mixed format
        f.write("\n\n")
        f.write("7) 일곱 번째 - 전환점\n\n")
        f.write("혼합 형식 챕터입니다. " * 120 + "\n\n")
        
        # Chapter 8: Plain sentence
        f.write("\n\n")
        f.write("운명의 만남\n\n")
        f.write("평범한 문장 제목입니다. " * 120 + "\n\n")
        
        # Chapter 9: Back to standard
        f.write("\n\n")
        f.write("9화 반전\n\n")
        f.write("아홉 번째 챕터입니다. " * 120 + "\n\n")
        
        # Chapter 10: Epilogue
        f.write("\n\n")
        f.write("에필로그: 끝과 시작\n\n")
        f.write("에필로그 내용입니다. " * 100 + "\n\n")


def demo_advanced_escalation():
    """Demonstrate the advanced escalation pipeline"""
    logger.info("=" * 80)
    logger.info("Stage 4 Advanced Escalation Demo")
    logger.info("=" * 80)
    
    # Create difficult test novel
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        test_file = f.name
    
    expected_chapters = 10
    create_difficult_novel(test_file, expected_chapters)
    
    logger.info(f"\n📚 Created test novel: {test_file}")
    logger.info(f"   Expected chapters: {expected_chapters}")
    logger.info(f"   File size: {os.path.getsize(test_file)/1024:.1f} KB")
    
    try:
        # Initialize components
        client = MockGeminiClient()
        structural = StructuralAnalyzer()
        scorer = AIScorer(client)
        optimizer = GlobalOptimizer()
        detector = TopicChangeDetector(client)
        
        # Stage 1: Structural Analysis
        logger.info("\n" + "=" * 80)
        logger.info("Stage 1: Structural Transition Point Analysis")
        logger.info("=" * 80)
        
        candidates = structural.generate_candidates(
            test_file,
            encoding='utf-8',
            max_candidates=expected_chapters * 5
        )
        
        logger.info(f"\n✅ Found {len(candidates)} structural candidates")
        logger.info("\nTop 5 candidates by confidence:")
        for i, cand in enumerate(sorted(candidates, key=lambda x: x['confidence'], reverse=True)[:5]):
            logger.info(f"  {i+1}. Line {cand['line_num']:3d}: {cand['text'][:40]:40s} (conf: {cand['confidence']:.2f})")
        
        # Stage 2: AI Scoring
        logger.info("\n" + "=" * 80)
        logger.info("Stage 2: AI Likelihood Scoring")
        logger.info("=" * 80)
        
        # Limit candidates for demo (to avoid too many API calls in real scenario)
        top_candidates = sorted(candidates, key=lambda x: x['confidence'], reverse=True)[:30]
        
        scored = scorer.score_candidates(
            test_file,
            top_candidates,
            encoding='utf-8',
            batch_size=5
        )
        
        logger.info(f"\n✅ Scored {len(scored)} candidates")
        logger.info("\nTop 5 by AI score:")
        for i, cand in enumerate(sorted(scored, key=lambda x: x.get('ai_score', 0), reverse=True)[:5]):
            logger.info(f"  {i+1}. Line {cand['line_num']:3d}: {cand['text'][:40]:40s} (AI: {cand.get('ai_score', 0):.2f})")
        
        # Stage 3: Topic Change Detection (if needed)
        logger.info("\n" + "=" * 80)
        logger.info("Stage 3: Topic Change Detection (Fallback)")
        logger.info("=" * 80)
        
        if len(scored) < expected_chapters * 2:
            topic_candidates = detector.detect_topic_boundaries(
                test_file,
                expected_chapters,
                existing_candidates=scored,
                encoding='utf-8'
            )
            
            if topic_candidates:
                logger.info(f"\n✅ Added {len(topic_candidates)} topic-change candidates")
                scored.extend(topic_candidates)
            else:
                logger.info("\nℹ️  No additional topic-change candidates needed")
        else:
            logger.info(f"\nℹ️  Sufficient candidates ({len(scored)}), skipping topic detection")
        
        # Stage 4: Global Optimization
        logger.info("\n" + "=" * 80)
        logger.info("Stage 4: Global Optimization")
        logger.info("=" * 80)
        
        selected = optimizer.select_optimal_boundaries(
            scored,
            expected_chapters,
            test_file,
            encoding='utf-8'
        )
        
        logger.info(f"\n✅ Selected {len(selected)} optimal boundaries")
        logger.info(f"   Target: {expected_chapters} chapters")
        logger.info(f"   Match: {'✅ EXACT' if len(selected) == expected_chapters else '⚠️  PARTIAL'}")
        
        logger.info("\nSelected chapter boundaries:")
        for i, sel in enumerate(selected):
            combined_score = sel.get('combined_score', 0)
            logger.info(f"  Chapter {i+1:2d}: Line {sel['line_num']:3d} - {sel['text'][:50]:50s} (score: {combined_score:.2f})")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("Pipeline Summary")
        logger.info("=" * 80)
        
        logger.info(f"\nStructural candidates generated: {len(candidates)}")
        logger.info(f"Candidates scored by AI:         {len(scored)}")
        logger.info(f"Final boundaries selected:        {len(selected)}")
        logger.info(f"Target chapter count:             {expected_chapters}")
        logger.info(f"Success rate:                     {len(selected)/expected_chapters*100:.0f}%")
        
        if len(selected) == expected_chapters:
            logger.info("\n🎉 SUCCESS: Achieved exact chapter count!")
        else:
            logger.info(f"\n⚠️  PARTIAL: {abs(len(selected) - expected_chapters)} chapters off target")
        
        logger.info("\n" + "=" * 80)
        logger.info("Demo Complete")
        logger.info("=" * 80)
        
    finally:
        # Cleanup
        os.unlink(test_file)
        logger.info(f"\n🗑️  Cleaned up test file")


if __name__ == "__main__":
    demo_advanced_escalation()
