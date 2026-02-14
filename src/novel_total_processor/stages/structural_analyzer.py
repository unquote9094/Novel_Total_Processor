"""Structural Analyzer for Transition Point Detection

Identifies potential chapter boundaries using structural cues:
- Line length shifts (short lines indicating titles)
- Blank line patterns
- Punctuation patterns
- Time/place markers
- Paragraph breaks

Does not rely on specific markers like numbers or brackets.
"""

import re
from typing import List, Dict, Any
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


class StructuralAnalyzer:
    """Detects potential chapter boundaries using structural cues"""
    
    # Structural analysis constants
    SHORT_LINE_THRESHOLD = 50  # Lines shorter than this are potential titles
    LONG_LINE_THRESHOLD = 200  # Long lines are likely body text
    MIN_BLANK_LINES = 1  # Minimum blank lines before a potential chapter
    CONTEXT_LINES = 3  # Lines to check before/after for context
    MAX_DIALOGUE_LENGTH = 40  # Maximum length for short dialogue/exclamation detection
    
    # Punctuation patterns that suggest chapter boundaries
    CHAPTER_INDICATORS = [
        r'^[第章]',  # Chinese chapter markers
        r'^\s*[IVX]+\.',  # Roman numerals
        r'^\s*Chapter',  # English chapter
        r'^\s*Part\s+\d+',  # Part markers
        r'^\s*===+',  # Separator lines
        r'^\s*---+',  # Separator lines
        r'^\s*\*\*\*+',  # Asterisk separators
    ]
    
    # Time/place markers
    TIME_PLACE_MARKERS = [
        r'^\s*\d{4}년',  # Year in Korean
        r'^\s*\d+월\s+\d+일',  # Date in Korean
        r'^\s*[一二三四五六七八九十]+年',  # Year in Chinese
        r'^\s*\[.*?(?:년|월|일|time|place|location)\]',  # Bracketed time/place
        r'^\s*(?:서울|도쿄|뉴욕|런던|파리)',  # Major cities
    ]
    
    def __init__(self):
        self.indicator_patterns = [re.compile(p, re.IGNORECASE) for p in self.CHAPTER_INDICATORS]
        self.time_place_patterns = [re.compile(p, re.IGNORECASE) for p in self.TIME_PLACE_MARKERS]
    
    def generate_candidates(
        self,
        file_path: str,
        encoding: str = 'utf-8',
        max_candidates: int = 1000
    ) -> List[Dict[str, Any]]:
        """Generate transition point candidates using structural cues
        
        Args:
            file_path: Path to the text file
            encoding: File encoding
            max_candidates: Maximum number of candidates to return
            
        Returns:
            List of candidate dictionaries with:
            - line_num: Line number (0-indexed)
            - text: The candidate line text
            - confidence: Initial confidence score (0.0-1.0)
            - features: Dict of detected features
        """
        candidates = []
        
        try:
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                lines = f.readlines()
            
            # Track context for better detection
            prev_blank_count = 0
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                
                # Skip very first line (often book title, not chapter)
                if i == 0:
                    continue
                
                # Track blank lines
                if not stripped:
                    prev_blank_count += 1
                    continue
                
                # Analyze this line for chapter boundary signals
                features = self._analyze_line_features(
                    stripped, 
                    i, 
                    lines,
                    prev_blank_count
                )
                
                # Calculate initial confidence based on features
                confidence = self._calculate_initial_confidence(features)
                
                # If confidence is above threshold, add as candidate
                if confidence > 0.3:  # Threshold to filter noise
                    candidates.append({
                        'line_num': i,
                        'text': stripped,
                        'confidence': confidence,
                        'features': features
                    })
                
                # Reset blank count after non-blank line
                prev_blank_count = 0
                
                # Limit candidates to prevent memory issues
                if len(candidates) >= max_candidates:
                    break
            
            # Filter candidates to maintain minimum line distance
            MIN_LINES_BETWEEN = 10
            filtered = []
            last_line = -MIN_LINES_BETWEEN
            for cand in sorted(candidates, key=lambda x: x['line_num']):
                if cand['line_num'] - last_line >= MIN_LINES_BETWEEN:
                    filtered.append(cand)
                    last_line = cand['line_num']
            
            logger.info(f"   🔍 Structural analysis: {len(filtered)} candidates generated (filtered from {len(candidates)} with min distance)")
            
            return filtered
            
        except Exception as e:
            logger.error(f"Error during structural analysis: {e}")
            return []
    
    def _analyze_line_features(
        self,
        line: str,
        line_num: int,
        all_lines: List[str],
        blank_lines_before: int
    ) -> Dict[str, Any]:
        """Analyze a single line for chapter boundary features
        
        Returns dict with boolean/numeric features
        """
        features = {
            'is_short': len(line) < self.SHORT_LINE_THRESHOLD,
            'is_very_short': len(line) < 30,
            'has_blank_before': blank_lines_before >= self.MIN_BLANK_LINES,
            'blank_count_before': blank_lines_before,
            'has_chapter_indicator': False,
            'has_time_place': False,
            'has_number': bool(re.search(r'\d+', line)),
            'has_brackets': bool(re.search(r'[\[\]【】]', line)),
            'has_punctuation_end': bool(re.search(r'[.!?。！？]$', line)),
            'is_all_caps': line.isupper() if len(line) > 0 else False,
            'starts_with_caps': line[0].isupper() if len(line) > 0 else False,
            'word_count': len(line.split()),
        }
        
        # Check for dialogue (quoted text or short exclamations)
        features['is_dialogue'] = bool(re.match(r'^["\'「『"].+["\'」』"]$', line)) or \
                                   bool(re.match(rf'^.{{1,{self.MAX_DIALOGUE_LENGTH}}}[?!？！]$', line))
        
        # Check for sentence endings (but not chapter indicators)
        features['is_sentence'] = bool(re.search(r'[.。다요죠습]$', line)) and not features.get('has_chapter_indicator')
        
        # Check for chapter indicators
        for pattern in self.indicator_patterns:
            if pattern.search(line):
                features['has_chapter_indicator'] = True
                break
        
        # Check for time/place markers
        for pattern in self.time_place_patterns:
            if pattern.search(line):
                features['has_time_place'] = True
                break
        
        # Check context: are following lines longer (suggesting this is a title)?
        if line_num + 1 < len(all_lines):
            next_line = all_lines[line_num + 1].strip()
            if next_line and len(next_line) > len(line) * 1.5:
                features['longer_lines_after'] = True
            else:
                features['longer_lines_after'] = False
        
        # Check if preceded by long lines (suggesting transition)
        if line_num > 0:
            prev_line = all_lines[line_num - 1].strip()
            if prev_line and len(prev_line) > self.LONG_LINE_THRESHOLD:
                features['long_line_before'] = True
            else:
                features['long_line_before'] = False
        
        return features
    
    def _calculate_initial_confidence(self, features: Dict[str, Any]) -> float:
        """Calculate initial confidence score based on structural features
        
        Returns:
            Confidence score 0.0-1.0
        """
        score = 0.0
        
        # Short line is a strong signal
        if features['is_short']:
            score += 0.3
        if features['is_very_short']:
            score += 0.2
        
        # Blank lines before are important
        if features['has_blank_before']:
            score += 0.2
        if features['blank_count_before'] >= 2:
            score += 0.1
        
        # Chapter indicators are very strong
        if features['has_chapter_indicator']:
            score += 0.4
        
        # Numbers are common in chapters
        if features['has_number']:
            score += 0.15
        
        # Brackets often indicate chapters
        if features['has_brackets']:
            score += 0.1
        
        # Time/place markers
        if features['has_time_place']:
            score += 0.2
        
        # Context signals
        if features.get('longer_lines_after'):
            score += 0.15
        if features.get('long_line_before'):
            score += 0.1
        
        # Caps can indicate titles
        if features['is_all_caps'] and 5 < features['word_count'] < 15:
            score += 0.15
        
        # Apply penalties for dialogue and sentences
        # Note: Penalties can drive scores negative before clamping to [0, 1]
        # This ensures dialogue/sentences are strongly discouraged as candidates
        if features.get('is_dialogue'):
            score -= 0.4  # Strong penalty for dialogue
        if features.get('is_sentence'):
            score -= 0.3  # Penalty for regular sentences
        
        # Normalize to 0-1 range (clamp both lower and upper bounds)
        return min(1.0, max(0.0, score))
