"""Topic Change Detector for Semantic Boundary Detection

Detects chapter boundaries based on semantic/topic changes in the text.
Used as a fallback when structural and AI methods are insufficient.
"""

import re
from typing import List, Dict, Any, Optional
from novel_total_processor.ai.gemini_client import GeminiClient
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


class TopicChangeDetector:
    """Detects semantic boundaries based on topic changes"""
    
    # Analysis constants
    WINDOW_SIZE = 2000         # Characters per analysis window
    WINDOW_OVERLAP = 500       # Overlap between windows
    MIN_CHANGE_CONFIDENCE = 0.6  # Minimum confidence for topic change
    
    def __init__(self, client: GeminiClient):
        """
        Args:
            client: GeminiClient for semantic analysis
        """
        self.client = client
    
    def detect_topic_boundaries(
        self,
        file_path: str,
        expected_count: int,
        existing_candidates: Optional[List[Dict[str, Any]]] = None,
        encoding: str = 'utf-8'
    ) -> List[Dict[str, Any]]:
        """Detect chapter boundaries based on topic/semantic changes
        
        Uses a sliding window approach:
        1. Divide text into overlapping windows
        2. Detect topic changes between windows using AI
        3. Identify strong transition points
        4. Return as candidates to merge with existing
        
        Args:
            file_path: Path to text file
            expected_count: Expected number of chapters
            existing_candidates: Optional existing candidates to avoid duplicates
            encoding: File encoding
            
        Returns:
            List of topic-change candidates with confidence scores
        """
        try:
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file for topic detection: {e}")
            return []
        
        # Calculate how many windows we need
        total_chars = len(content)
        stride = self.WINDOW_SIZE - self.WINDOW_OVERLAP
        num_windows = max(1, (total_chars - self.WINDOW_SIZE) // stride + 1)
        
        # Adjust window count based on expected chapters
        # We want roughly 2-3x expected count to ensure good coverage
        target_windows = min(num_windows, expected_count * 3)
        
        if target_windows < num_windows:
            # Adjust stride to fit target windows
            stride = max(1, (total_chars - self.WINDOW_SIZE) // target_windows)
        
        logger.info(f"   🔍 Topic detection: Analyzing {target_windows} windows")
        
        # Analyze windows for topic changes
        candidates = []
        existing_positions = set()
        
        if existing_candidates:
            # Get approximate character positions of existing candidates
            try:
                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                    lines = f.readlines()
                
                for cand in existing_candidates:
                    line_num = cand.get('line_num', 0)
                    char_pos = sum(len(line) for line in lines[:line_num])
                    existing_positions.add(char_pos)
            except:
                pass
        
        for i in range(target_windows):
            start_pos = i * stride
            end_pos = min(start_pos + self.WINDOW_SIZE, total_chars)
            
            if start_pos >= total_chars:
                break
            
            # Get window text
            window_text = content[start_pos:end_pos]
            
            # Skip if this overlaps with existing candidate
            if self._overlaps_existing(start_pos, existing_positions):
                continue
            
            # Analyze for topic change at this boundary
            if i > 0:  # Skip first window (no previous context)
                prev_start = max(0, start_pos - stride)
                prev_text = content[prev_start:start_pos]
                
                # Detect topic change between prev_text and window_text
                change_score = self._detect_topic_change(prev_text, window_text)
                
                if change_score >= self.MIN_CHANGE_CONFIDENCE:
                    # Find the best boundary point within the window
                    boundary_pos = self._find_boundary_in_window(
                        window_text,
                        start_pos
                    )
                    
                    # Convert char position to line number
                    line_num = content[:boundary_pos].count('\n')
                    
                    candidates.append({
                        'line_num': line_num,
                        'text': self._get_line_at_position(content, boundary_pos),
                        'confidence': change_score,
                        'ai_score': change_score,
                        'source': 'topic_change',
                        'byte_pos': boundary_pos
                    })
        
        logger.info(f"   ✅ Topic detection: Found {len(candidates)} topic-change boundaries")
        
        return candidates
    
    def _detect_topic_change(
        self,
        prev_text: str,
        current_text: str
    ) -> float:
        """Detect topic change between two text segments using AI
        
        Args:
            prev_text: Previous text segment
            current_text: Current text segment
            
        Returns:
            Confidence score 0.0-1.0 that a topic change occurred
        """
        # Truncate texts for API efficiency
        prev_sample = prev_text[-1000:] if len(prev_text) > 1000 else prev_text
        curr_sample = current_text[:1000] if len(current_text) > 1000 else current_text
        
        prompt = f"""=== topic_change_detection ===
You are an expert in analyzing narrative structure.

[Task]
Determine if there is a significant topic/scene change between TEXT A and TEXT B.
Return ONLY a numeric score from 0.0 to 1.0, where:
- 1.0 = Clear topic/scene change (new chapter likely)
- 0.5 = Moderate change (possible transition)
- 0.0 = Same topic/scene continues

[TEXT A - Previous]
{prev_sample}

[TEXT B - Current]
{curr_sample}

[Indicators of Topic Change]
- New location/setting
- New time period
- New character focus
- New plot thread
- Scene break or transition
- Perspective change

Return ONLY the numeric score. No explanation.
"""
        
        try:
            response = self.client.generate_content(prompt)
            score_str = response.strip()
            
            # Extract score
            import re
            numbers = re.findall(r'0?\.\d+|1\.0|0|1', score_str)
            if numbers:
                score = float(numbers[0])
                return max(0.0, min(1.0, score))
            else:
                return 0.5
        except Exception as e:
            logger.warning(f"Topic change detection error: {e}")
            return 0.5
    
    def _find_boundary_in_window(
        self,
        window_text: str,
        window_start_pos: int
    ) -> int:
        """Find the best boundary point within a window
        
        Looks for paragraph breaks, blank lines, or short lines
        that would make good chapter boundaries.
        
        Args:
            window_text: The window text
            window_start_pos: Character position where window starts
            
        Returns:
            Absolute character position of best boundary
        """
        # Look for paragraph breaks (double newlines)
        double_newline = re.search(r'\n\s*\n', window_text)
        if double_newline:
            return window_start_pos + double_newline.start()
        
        # Look for single newline with short line after
        lines = window_text.split('\n')
        for i, line in enumerate(lines[:-1]):
            if len(line.strip()) < 50 and i > 0:
                # Count chars up to this line
                chars_before = sum(len(l) + 1 for l in lines[:i])
                return window_start_pos + chars_before
        
        # Default: use window start
        return window_start_pos
    
    def _get_line_at_position(
        self,
        content: str,
        char_pos: int
    ) -> str:
        """Get the text line at a given character position
        
        Args:
            content: Full file content
            char_pos: Character position
            
        Returns:
            The line text at that position
        """
        # Find line boundaries around this position
        start = content.rfind('\n', 0, char_pos) + 1
        end = content.find('\n', char_pos)
        if end == -1:
            end = len(content)
        
        return content[start:end].strip()
    
    def _overlaps_existing(
        self,
        position: int,
        existing_positions: set,
        threshold: int = 5000
    ) -> bool:
        """Check if position overlaps with existing candidates
        
        Args:
            position: Character position to check
            existing_positions: Set of existing candidate positions
            threshold: Distance threshold for overlap
            
        Returns:
            True if overlaps with any existing position
        """
        for existing in existing_positions:
            if abs(position - existing) < threshold:
                return True
        return False
