"""AI Scorer for Chapter Title Likelihood

Scores each candidate line with surrounding context to determine
likelihood that it's a true chapter title boundary.
"""

import re
import time
from typing import List, Dict, Any, Optional
from novel_total_processor.ai.gemini_client import GeminiClient
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


class AIScorer:
    """Scores chapter title candidates using AI"""
    
    # Scoring constants
    CONTEXT_LINES_BEFORE = 5  # Lines of context before candidate
    CONTEXT_LINES_AFTER = 5   # Lines of context after candidate
    BATCH_SIZE = 10           # Score candidates in batches
    RATE_LIMIT_DELAY = 0.5    # Seconds between API calls
    
    def __init__(self, client: GeminiClient):
        """
        Args:
            client: GeminiClient instance for API calls
        """
        self.client = client
    
    def score_candidates(
        self,
        file_path: str,
        candidates: List[Dict[str, Any]],
        encoding: str = 'utf-8',
        batch_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Score each candidate for chapter title likelihood
        
        Args:
            file_path: Path to the text file
            candidates: List of candidate dicts with 'line_num' and 'text'
            encoding: File encoding
            batch_size: Optional batch size override
            
        Returns:
            Updated candidates with 'ai_score' field (0.0-1.0)
        """
        if not candidates:
            return candidates
        
        batch_size = batch_size or self.BATCH_SIZE
        
        # Read file lines once
        try:
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Failed to read file for AI scoring: {e}")
            return candidates
        
        # Process candidates in batches
        total_candidates = len(candidates)
        logger.info(f"   🤖 AI Scoring: Processing {total_candidates} candidates in batches of {batch_size}")
        
        scored_count = 0
        for i in range(0, total_candidates, batch_size):
            batch = candidates[i:i + batch_size]
            
            for candidate in batch:
                # Get context around the candidate
                context = self._get_context(
                    lines,
                    candidate['line_num']
                )
                
                # Score this candidate
                score = self._score_single_candidate(
                    candidate['text'],
                    context
                )
                
                candidate['ai_score'] = score
                scored_count += 1
                
                # Rate limiting
                if scored_count < total_candidates:
                    time.sleep(self.RATE_LIMIT_DELAY)
            
            if scored_count < total_candidates:
                logger.info(f"   🤖 Scored {scored_count}/{total_candidates} candidates...")
        
        logger.info(f"   ✅ AI Scoring complete: {scored_count} candidates scored")
        
        return candidates
    
    def _get_context(
        self,
        lines: List[str],
        line_num: int
    ) -> Dict[str, str]:
        """Extract context lines around a candidate
        
        Returns:
            Dict with 'before', 'candidate', 'after' text
        """
        # Get lines before (excluding blanks at boundaries)
        start_idx = max(0, line_num - self.CONTEXT_LINES_BEFORE)
        before_lines = [l.strip() for l in lines[start_idx:line_num] if l.strip()]
        before_text = '\n'.join(before_lines[-self.CONTEXT_LINES_BEFORE:])
        
        # Candidate line
        candidate_text = lines[line_num].strip() if line_num < len(lines) else ""
        
        # Get lines after
        end_idx = min(len(lines), line_num + 1 + self.CONTEXT_LINES_AFTER)
        after_lines = [l.strip() for l in lines[line_num + 1:end_idx] if l.strip()]
        after_text = '\n'.join(after_lines[:self.CONTEXT_LINES_AFTER])
        
        return {
            'before': before_text,
            'candidate': candidate_text,
            'after': after_text
        }
    
    def _score_single_candidate(
        self,
        candidate_line: str,
        context: Dict[str, str]
    ) -> float:
        """Score a single candidate using AI
        
        Args:
            candidate_line: The candidate title line
            context: Context dict with before/after text
            
        Returns:
            Likelihood score 0.0-1.0
        """
        prompt = f"""=== chapter_title_likelihood ===
You are an expert in analyzing novel structures.

[Task]
Evaluate whether the CANDIDATE line below is a chapter title/boundary.
Return ONLY a numeric score from 0.0 to 1.0, where:
- 1.0 = Definitely a chapter title
- 0.5 = Possibly a chapter title
- 0.0 = Definitely NOT a chapter title

[Context Before]
{context['before']}

[CANDIDATE LINE]
>>> {candidate_line} <<<

[Context After]
{context['after']}

[Scoring Criteria]
- Short, standalone lines are more likely to be titles
- Lines with chapter numbers/markers are strong indicators
- Lines that clearly continue a sentence are NOT titles
- Lines followed by narrative text are more likely to be titles
- Dialogue lines are NOT titles

Return ONLY the numeric score (e.g., 0.8). No explanation.
"""
        
        try:
            response = self.client.generate_content(prompt)
            # Extract numeric score from response
            score_str = response.strip()
            
            # Try to extract a number from the response
            numbers = re.findall(r'0?\.\d+|1\.0|0|1', score_str)
            if numbers:
                score = float(numbers[0])
                # Ensure in valid range
                score = max(0.0, min(1.0, score))
                return score
            else:
                logger.warning(f"Could not parse AI score from: {score_str[:50]}")
                return 0.5  # Default to neutral score
                
        except Exception as e:
            logger.warning(f"AI scoring error: {e}")
            return 0.5  # Default to neutral score on error
