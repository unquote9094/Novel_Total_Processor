# Task: Stage 4 Chapter Splitting & Stage 2/5 Enhancement

## Context
- TXT 파일 분할 및 EPUB 생성 로직 개선 필요
- 기존 Stage 2/5의 비효율성 개선 및 검증 시스템 도입 필요
- NovelAIze-SSR v3.0의 검증된 로직 포팅 필요

## Goal
- Stage 4 챕터 분할 구현 (NovelAIze-SSR v3.0 포팅)
- Stage 2 화수 검증 개선 (Stage 4 결과 활용)
- Stage 5 EPUB 생성 개선 (다중 챕터, 계층형 목차, EPUB 보강)
- 검증 시스템 도입 및 UI 개선

## Plan
1. **Stage 4 구현**: 챕터 분할, 소제목 추출, AI 패턴 분석, Adaptive Retry
2. **Stage 2 개선**: Stage 4 완료 파일 대상 처리, AI 호출 최소화
3. **Stage 5 개선**: 다중 챕터 지원, 계층형 목차 생성, 기존 EPUB 파일 보강
4. **검증 시스템**: EPUB 무결성 검증 도구 개발
5. **UI/UX 개선**: DB 뷰어, 폴더 선택, 검증 메뉴 추가

## Done
- [x] **Stage 4 챕터 분할**: Sampler, Splitter, PatternManager, ChapterSplitRunner 구현 (완료)
- [x] **Stage 2 화수 검증**: Stage 4 결과 활용하여 AI 호출 제거 (완료)
- [x] **Stage 5 EPUB**: 다중 챕터, 계층형 목차, EPUB 보강, Helper Method (완료)
- [x] **검증 시스템**: EPUBVerifier 10가지 항목 검증, DB Viewer 구현 (완료)
- [x] **UI**: 메뉴 및 설정 개선, 파이프라인 순서 변경 (완료)
