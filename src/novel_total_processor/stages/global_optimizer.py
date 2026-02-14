"""Global Optimizer for Chapter Boundary Selection

Selects exactly the expected number of chapter boundaries from scored candidates,
maximizing total score while respecting spacing constraints.
"""

import os
from typing import List, Dict, Any, Optional
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


class GlobalOptimizer:
    """Selects optimal chapter boundaries using global optimization"""
    
    # Optimization constants
    MIN_CHAPTER_LENGTH = 1000  # Minimum characters between chapters
    MIN_CHAPTER_RATIO = 0.3    # Minimum chapter size as ratio of average
    
    def __init__(self):
        pass
    
    def select_optimal_boundaries(
        self,
        candidates: List[Dict[str, Any]],
        expected_count: int,
        file_path: str,
        encoding: str = 'utf-8'
    ) -> List[Dict[str, Any]]:
        """Select exactly expected_count boundaries using global optimization
        
        Uses a greedy algorithm with spacing constraints:
        1. Sort candidates by combined score (structural + AI)
        2. Select highest-scoring candidates
        3. Enforce minimum distance between selections
        4. Ensure reasonable chapter length distribution
        
        Args:
            candidates: List of scored candidate dicts
            expected_count: Number of chapters to select
            file_path: Path to file (for size calculations)
            encoding: File encoding
            
        Returns:
            List of selected candidates (subset of input)
        """
        if not candidates or expected_count <= 0:
            return []
        
        # Calculate combined scores
        scored_candidates = self._calculate_combined_scores(candidates)
        
        # Get file size for distance calculations
        try:
            file_size = os.path.getsize(file_path)
            
            # Read file to calculate line positions
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                lines = f.readlines()
            
            # Add position in bytes to each candidate
            for cand in scored_candidates:
                line_num = cand['line_num']
                # Calculate approximate byte position
                cand['byte_pos'] = sum(len(line.encode(encoding, errors='replace')) 
                                      for line in lines[:line_num])
        except Exception as e:
            logger.warning(f"Could not calculate positions: {e}")
            file_size = 0
            for cand in scored_candidates:
                cand['byte_pos'] = cand['line_num'] * 1000  # Rough estimate
        
        # Calculate typical chapter size
        avg_chapter_size = file_size / expected_count if expected_count > 0 else 50000
        min_distance = max(
            self.MIN_CHAPTER_LENGTH,
            int(avg_chapter_size * self.MIN_CHAPTER_RATIO)
        )
        
        logger.info(f"   🎯 Optimizer: Selecting {expected_count} from {len(candidates)} candidates")
        logger.info(f"   📏 Min chapter distance: {min_distance/1024:.1f}KB (avg: {avg_chapter_size/1024:.1f}KB)")
        
        # Sort by combined score (descending)
        scored_candidates.sort(key=lambda x: x['combined_score'], reverse=True)
        
        # Greedy selection with spacing constraints
        selected = []
        
        for candidate in scored_candidates:
            # Check if we've selected enough
            if len(selected) >= expected_count:
                break
            
            # Check minimum distance from all previously selected
            if self._is_valid_selection(candidate, selected, min_distance):
                selected.append(candidate)
        
        # If we didn't get enough, relax constraints and try again
        if len(selected) < expected_count:
            logger.warning(f"   ⚠️  Only found {len(selected)}/{expected_count} with strict spacing")
            logger.info(f"   🔄 Relaxing constraints to meet target count...")
            
            # Try with reduced minimum distance
            relaxed_distance = int(min_distance * 0.5)
            selected = []
            
            for candidate in scored_candidates:
                if len(selected) >= expected_count:
                    break
                
                if self._is_valid_selection(candidate, selected, relaxed_distance):
                    selected.append(candidate)
        
        # If still not enough, just take top N by score (no spacing constraint)
        if len(selected) < expected_count:
            logger.warning(f"   ⚠️  Still only {len(selected)}/{expected_count} with relaxed spacing")
            logger.info(f"   🔄 Using top-N selection without spacing constraints...")
            
            # Take top candidates by score, ensuring no duplicates
            selected = []
            seen_positions = set()
            
            for candidate in scored_candidates:
                if len(selected) >= expected_count:
                    break
                
                pos = candidate['byte_pos']
                if pos not in seen_positions:
                    selected.append(candidate)
                    seen_positions.add(pos)
        
        # Sort by position for final output
        selected.sort(key=lambda x: x['byte_pos'])
        
        logger.info(f"   ✅ Optimizer: Selected {len(selected)} boundaries")
        
        # [Debug Logging] Show boundary details
        if selected:
            logger.info(f"   📊 Boundary format details:")
            logger.info(f"      → Type: line_num (0-indexed line numbers) + byte_pos + text")
            logger.info(f"      → Count: {len(selected)} boundaries selected")
            logger.info(f"      → Sample (first 3):")
            for i, sel in enumerate(selected[:3]):
                logger.info(f"         {i+1}. line={sel['line_num']}, pos={sel['byte_pos']}, score={sel.get('combined_score', 0):.2f}")
        
        return selected
    
    def _calculate_combined_scores(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Calculate combined score from structural confidence and AI score
        
        Weighted combination:
        - AI score (if available): 70%
        - Structural confidence: 30%
        """
        scored = []
        
        for cand in candidates:
            structural_score = cand.get('confidence', 0.5)
            ai_score = cand.get('ai_score', structural_score)  # Fallback to structural
            
            # Weighted combination
            combined = (ai_score * 0.7) + (structural_score * 0.3)
            
            cand_copy = cand.copy()
            cand_copy['combined_score'] = combined
            scored.append(cand_copy)
        
        return scored
    
    def _is_valid_selection(
        self,
        candidate: Dict[str, Any],
        selected: List[Dict[str, Any]],
        min_distance: int
    ) -> bool:
        """Check if candidate is valid given already selected boundaries
        
        Args:
            candidate: Candidate to check
            selected: Already selected candidates
            min_distance: Minimum byte distance required
            
        Returns:
            True if candidate maintains minimum distance from all selected
        """
        if not selected:
            return True
        
        candidate_pos = candidate['byte_pos']
        
        for sel in selected:
            sel_pos = sel['byte_pos']
            distance = abs(candidate_pos - sel_pos)
            
            if distance < min_distance:
                return False
        
        return True
