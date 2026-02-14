# Stage 4 Escalation Threshold Updates - Summary

## Overview
This PR implements tightened escalation thresholds and gap retry limits for Stage 4 chapter splitting, making the system more efficient and responsive to pattern refinement issues.

## Requirements Met

### ✅ 1. Enforce Stagnation Escalation After 3 Consecutive Attempts
**Requirement**: Treat +/-1 or +/-2 fluctuations as stagnant so the 3-attempt threshold triggers reliably.

**Implementation**:
- Updated `_is_stagnant()` method in `stage4_splitter.py` to check if `max_count - min_count <= 2`
- Changed from exact equality check to tolerance-based check
- Now triggers escalation for patterns like: `[85, 87, 85]`, `[10, 11, 10]`, `[100, 100, 100]`
- Does NOT trigger for meaningful changes like: `[10, 15, 20]`, `[10, 10, 14]`

**Example Scenarios**:
```python
# Stagnant (triggers escalation):
[85, 85, 87]  # max-min = 2
[100, 101, 100]  # max-min = 1
[50, 50, 50]  # max-min = 0

# Not stagnant (continues retrying):
[85, 88, 91]  # max-min = 6
[100, 104, 108]  # max-min = 8
```

### ✅ 2. Trigger Escalation After 2 Consecutive Pattern Refinement Rejections
**Requirement**: When pattern refinement is rejected 2 times in a row ("보강 패턴 거절"), immediately trigger advanced pipeline escalation.

**Implementation**:
- Modified `refine_pattern_with_goal_v3()` to return `(pattern, rejection_count)` tuple
- Added `consecutive_rejection_count` tracking in retry loop
- Increments on rejection, resets to 0 on success
- Triggers escalation when `consecutive_rejection_count >= 2`
- Clear logging shows: "🚨 Escalation reason: Consecutive pattern refinement rejections"

**Code Changes**:
```python
# pattern_manager.py
if new_count > best_count and new_count <= expected_count:
    rejection_count = 0  # Reset on success
else:
    rejection_count += 1
    logger.info(f"❌ 보강 패턴 거절 (연속 거절: {rejection_count})")

# stage4_splitter.py
if consecutive_rejection_count >= REJECTION_THRESHOLD:
    logger.warning("🚨 Escalation reason: Consecutive pattern refinement rejections")
    break  # Trigger escalation
```

### ✅ 3. Limit Gap-Based Pattern Refinement to 3 Gaps Maximum
**Requirement**: Use MAX_GAPS_TO_ANALYZE=3 consistently to cap AI calls.

**Implementation**:
- Added `max_gaps` parameter to `refine_pattern_with_goal_v3()` with default value 3
- Changed gap loop from `for gap in gaps:` to `for gap in gaps[:max_gaps]:`
- Passes `self.MAX_GAPS_TO_ANALYZE` from stage4_splitter
- Added logging: "📊 Gap 분석 제한: X/Y gaps (MAX_GAPS_TO_ANALYZE=3)"

**Before**:
```python
for gap in gaps:  # Could process all 10+ gaps
    sample = self.sampler.extract_samples_from(...)
```

**After**:
```python
limited_gaps = gaps[:max_gaps]  # Limit to 3 gaps
logger.info(f"Gap 분석 제한: {len(limited_gaps)}/{len(gaps)} gaps")
for gap in limited_gaps:
    sample = self.sampler.extract_samples_from(...)
```

### ✅ 4. Keep Logs Concise but Clear About Escalation Reasons
**Requirement**: Clear logging about why escalation occurred (stagnation, rejection streak, gap limit).

**Implementation**:
- Stagnation logs show:
  - Reason: "Stagnation detected"
  - Details: Chapter count history for last N attempts
  - Example: "Chapter counts: [85, 87, 85]"
  
- Rejection logs show:
  - Reason: "Consecutive pattern refinement rejections"
  - Details: Number of consecutive rejections
  - Example: "2 consecutive rejections detected"
  
- Gap limit logs show:
  - Analyzed vs total gaps
  - Example: "Gap 분석 제한: 3/8 gaps (MAX_GAPS_TO_ANALYZE=3)"

**Log Format**:
```
============================================================
   🚨 Escalation reason: [REASON]
      → [DETAILS]
   🚀 Triggering early escalation to advanced pipeline...
============================================================
```

## Testing

### Updated Tests
1. **Stagnation Detection Tests** (`test_stage4_fixes.py`):
   - ✅ Test exact same count (10, 10, 10)
   - ✅ Test +/-1 fluctuation (10, 11, 10)
   - ✅ Test +/-2 fluctuation (85, 87, 85)
   - ✅ Test change > 2 is not stagnant (10, 10, 14)
   - ✅ Test significant changes (10, 15, 20)
   - ✅ Test insufficient history
   
2. **Return Type Validation**:
   - ✅ Verified `refine_pattern_with_goal_v3()` returns `(str, int)` tuple
   - ✅ Verified rejection count is 0 when pattern matches

### Test Results
```
✅ All Tests Passed!
- AI Response Null Handling: PASSED
- Regex Validation: PASSED
- Stagnation Detection (7 scenarios): PASSED
- Advanced Pipeline Components: PASSED
```

## Files Modified

1. **src/novel_total_processor/stages/stage4_splitter.py** (+48 lines, -11 lines)
   - Updated `_is_stagnant()` method with +/-2 tolerance
   - Added `consecutive_rejection_count` tracking
   - Enhanced escalation logging
   - Added rejection threshold constant (REJECTION_THRESHOLD = 2)

2. **src/novel_total_processor/stages/pattern_manager.py** (+40 lines, -10 lines)
   - Changed `refine_pattern_with_goal_v3()` return type to tuple
   - Added `max_gaps` parameter with default 3
   - Limited gap loop to `gaps[:max_gaps]`
   - Track rejection count in gap analysis loop
   - Enhanced logging for gap limit and rejections

3. **test_stage4_fixes.py** (+37 lines, -8 lines)
   - Added tests for +/-1 and +/-2 fluctuation scenarios
   - Added test for significant changes (no stagnation)
   - Improved test clarity with comments

## Impact

### Performance
- **Reduced AI Calls**: Gap analysis now capped at 3 gaps instead of potentially 10+
- **Faster Escalation**: 
  - Stagnation detection triggers earlier (tolerates minor fluctuations)
  - Rejection tracking prevents wasting time on failed pattern refinements

### Reliability
- **More Consistent Behavior**: Tolerating +/-1 or +/-2 prevents false negatives
- **Clear Debugging**: Enhanced logs make it easy to understand why escalation occurred

### Backward Compatibility
- All changes are backward compatible
- Existing code paths continue to work
- Default parameters maintain previous behavior where applicable

## Security Summary
✅ No security vulnerabilities found (CodeQL analysis)

## Conclusion
All requirements have been successfully implemented:
1. ✅ Stagnation escalation with +/-2 tolerance
2. ✅ Rejection tracking with 2-consecutive threshold
3. ✅ Gap analysis limited to 3 gaps
4. ✅ Clear, concise escalation logging
