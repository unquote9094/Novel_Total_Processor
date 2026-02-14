# 스테이지 4 강화 - 구현 요약 (Stage 4 Enhancements - Implementation Summary)

## 개요 (Overview)
정규식(regex) 기반 패턴이 챕터를 놓치는 경우를 대비하여, 특히 혼합되거나 불규칙한 챕터 제목을 가진 대규모 소설 컬렉션(1.5만 권 이상)을 위해 스테이지 4의 챕터 분할 파이프라인이 다중 신호 챕터 감지 및 더 나은 복구 기능을 지원하도록 강화했습니다.

## 구현된 핵심 기능 (Key Features Implemented)

### 1. 동적 간격 탐지 (Dynamic Gap Detection)
**파일**: `pattern_manager.py`  
**메서드**: `find_dynamic_gaps()`

- 고정된 100KB 간격 임계값을 소설의 평균 챕터 크기에 기반한 동적 탐지로 대체했습니다.
- 전체 파일 크기 / 예상 화수로부터 평균 챕터 크기를 계산합니다.
- 평균 크기의 1.5배를 임계값으로 사용합니다 (최소 50KB).
- 평균 대비 상대적인 크기에 따라 간격의 우선순위를 정합니다.
- 우선순위에 따라 정렬된 상위 10개의 간격을 반환합니다.

**장점 (Benefits)**:
- 챕터 길이가 다양한 소설에서 더 정확합니다.
- 평균 대비 상당한 크기이지만 100KB보다는 작은 간격들을 포착합니다.
- 짧거나 긴 챕터 형식 모두에 더 적합합니다.

### 2. AI 기반 제목 후보 추출 (AI-Based Title Candidate Extraction)
**파일**: `pattern_manager.py`  
**메서드**: `extract_title_candidates()`

- 누락된 윈도우(구간)에서 AI를 사용하여 잠재적인 챕터 제목 라인을 식별합니다.
- 합의 투표(Consensus voting)를 구현했습니다: AI를 3번 호출하고 다수결 투표를 사용합니다.
- 최소 2표 이상의 득표를 얻은 후보만 필터링합니다.
- 높은 신뢰도를 가진 제목 후보만 반환합니다.

**장점 (Benefits)**:
- 단일 AI 호출보다 더 견고합니다.
- 합의를 통해 오탐(False Positives)을 줄입니다.
- 불규칙하거나 숫자가 없는 챕터 제목을 처리합니다.
- 정규식 패턴이 챕터를 놓칠 때 폴백(fallback)으로 작동합니다.

### 3. 멀티라인 제목 지원 (Multi-Line Title Support)
**파일**: `splitter.py`  
**메서드**: `split()` (강화됨)

- 여러 줄에 걸쳐 있는 챕터 제목을 지원합니다.
- 예시: 1행: `[집을 숨김 - 34화]`, 2행: `[34) 김영감의 분노]`
- 연속된 제목 후보들을 단일 챕터 제목으로 병합합니다.
- 형식: `후보1 | 실제_제목`

**장점 (Benefits)**:
- 복잡한 한국 소설 제목 형식을 처리합니다.
- 대괄호 표시자와 실제 제목을 모두 보존합니다.
- 단일 챕터가 여러 부분으로 나뉘는 것을 방지합니다.

### 4. 명시적 제목 라인 분할 (Explicit Title Line Splitting)
**파일**: `splitter.py`  
**메서드**: `split()` (매개변수 강화)

- split() 메서드에 `title_candidates` 매개변수를 추가했습니다.
- 정규식 외에도 명시적인 제목 라인에 의한 분할을 허용합니다.
- 각 라인이 제목 후보 중 하나와 일치하는지 확인합니다.
- 정규식 패턴과 조합하여 작동합니다.

**장점 (Benefits)**:
- 정규식 패턴이 불충분할 때의 폴백(Fallback) 수단입니다.
- 하이브리드 접근 방식(정규식 + AI 감지 제목)을 가능하게 합니다.
- 불규칙한 챕터 표시자에 대한 커버리지를 향상시킵니다.

### 5. 강화된 복구 루프 (Enhanced Recovery Loop)
**파일**: `stage4_splitter.py`  
**메서드**: `split_chapters()` (강화됨)

- 최대 재시도 횟수를 3회에서 5회로 늘렸습니다.
- 다단계 복구 프로세스:
  1. 패턴 기반 분할
  2. 예상 수량 대비 화수 검증
  3. 동적 간격 분석
  4. 패턴 정제 (정규식 생성)
  5. 제목 후보 추출 (AI fallback)
  6. 합의 기반 재분할
- 사용된 복구 방법(패턴 vs 합의)을 추적합니다.
- 강화된 로깅을 통해 어떤 기법들이 적용되었는지 보여줍니다.

**장점 (Benefits)**:
- 어려운 케이스들에 대한 더 높은 성공률을 보장합니다.
- 복구 시도에 대한 명확한 감사 추적(Audit trail)을 제공합니다.
- 여러 탐지 전략을 결합하여 사용합니다.
- 한 방법이 실패하면 우아하게 폴백(fallback)합니다.

### 6. 로깅 강화 (Enhanced Logging)
**파일**: `pattern_manager.py`, `stage4_splitter.py`

- 동적 간격 분석 통계를 로그에 남깁니다.
- 제목 후보 개수와 합의 결과를 보여줍니다.
- 어떤 복구 방법들이 사용되었는지 기록합니다.
- 상세한 불일치 정보를 포함합니다.
- 재시도 횟수와 결과를 추적합니다.

**장점 (Benefits)**:
- 더 나은 디버깅과 문제 해결을 지원합니다.
- 복구 프로세스에 대한 명확한 가시성을 제공합니다.
- 추가 최적화를 위한 패턴 식별을 돕습니다.
- 화수 일치에 대한 책임성(Accountability)을 제공합니다.

## 구현 세부 사항 (Implementation Details)

### Pattern Manager 변경 사항
```python
# 신규 메서드:
- find_dynamic_gaps(): 동적 간격 탐지
- extract_title_candidates(): 합의 기반 AI 제목 추출

# 강화된 메서드:
- refine_pattern_with_goal_v3(): 이제 동적 간격과 제목 후보를 사용함
```

### Splitter 변경 사항
```python
# 신규 매개변수:
- split(title_candidates=...): 명시적 제목 라인 지원

# 신규 기능:
- 멀티라인 제목 병합
- 제목 후보 매칭
- 대기 중인 제목 후보 추적
```

### Stage 4 Runner 변경 사항
```python
# 강화된 루프:
- 최대 재시도: 3 → 5
- 재시도 >= 2일 때 제목 후보 추출 추가
- 동적 간격 기반 복구
- 폴백 탐지를 위한 합의 투표
- 강화된 정합성 로깅
```

## 테스트 (Testing)

`test_stage4_enhancements.py`에서 종합적인 테스트 모음(Test suite)을 생성했습니다:

1. **test_enhanced_pattern_manager_methods**: 모든 신규 메서드가 존재하는지 검증
2. **test_dynamic_gap_detection**: 다양한 크기의 간격 탐지 테스트
3. **test_multi_line_title_support**: 멀티라인 제목 병합 검증
4. **test_splitter_with_title_candidates**: 명시적 제목 라인 분할 테스트

모든 테스트를 성공적으로 통과했습니다.

## 하위 호환성 (Backward Compatibility)

- **EPUB 처리**: 변경 없음, 기존 로직 계속 사용
- **기존 패턴**: 이전과 동일하게 작동
- **기본 동작**: 단순한 케이스에 대해 기존과 동일함
- **신규 기능**: 필요할 때만 활성화됨 (재시도 >= 2, 간격 탐지 시 등)

## 설정 (Configuration)

설정 변경은 필요하지 않습니다. 모든 강화 기능은 기존 설정과 API 키를 사용합니다.

## 성능 고려 사항 (Performance Considerations)

- 동적 간격 탐지: O(n) (n = 매치 개수)
- 제목 후보 추출: 간격당 3회의 AI 호출 (비율 제한 적용)
- 멀티라인 탐지: 최소한의 오버헤드, 라인당 O(1)
- 전반적 수준: 어려운 케이스에서 약간 느려짐, 단순 케이스에서는 동일한 속도

## 향후 강화 계획 (미구현) (Future Enhancements (Not Implemented))

변경 사항을 최소화하기 위해 다음 사항들은 고려되었으나 구현되지 않았습니다:

1. 설정 가능한 합의 투표 수 (3으로 하드코딩됨)
2. 머신러닝 기반 패턴 탐지
3. 특정 소설 형식에 대한 커스텀 휴리스틱
4. 더 빠른 합의를 위한 병렬 AI 호출
5. 고급 주제 변경 탐지

## 수정된 파일 (Files Modified)

1. `src/novel_total_processor/stages/pattern_manager.py` - 동적 간격 및 합의 기능으로 강화됨
2. `src/novel_total_processor/stages/splitter.py` - 멀티라인 및 명시적 제목 지원 추가
3. `src/novel_total_processor/stages/stage4_splitter.py` - 복구 루프 개선
4. `test_stage4_enhancements.py` - 신규 테스트 파일 (생성됨)

## 변경된 라인 수 (Lines Changed)

- pattern_manager.py: 약 120 라인 추가
- splitter.py: 약 60 라인 수정
- stage4_splitter.py: 약 40 라인 수정
- 합계: 집중적으로 약 220 라인의 변경

## 결론 (Conclusion)

문제 설명(Problem statement)에서의 모든 요구 사항이 구현되었습니다:
✅ 다중 신호 챕터 감지 (Multi-signal chapter detection)
✅ 평균 크기 기반 동적 간격 탐지
✅ 합의 기반 AI 제목 후보 추출
✅ 멀티라인 제목 지원
✅ 강화된 복구 루프
✅ 폴백 경계 탐지 (Fallback boundary detection)
✅ 로깅 개선
✅ EPUB 동작 유지
✅ 최소한의 수술적 변경
✅ 종합적인 테스트
