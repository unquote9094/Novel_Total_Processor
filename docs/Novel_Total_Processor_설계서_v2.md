# Novel Total Processor — 종합 설계서 v2.0

> **문서 목적**: Codex 대화록 + Antigravity 참조 소스 분석 + 사용자 논의를 **모두 종합**한 마스터 설계 문서  
> **작성일**: 2026-02-12  
> **상태**: 사용자 최종 검토 필요

---

# Part 1: 확정된 사항

---

## 1. 프로젝트 개요

15,000개+ 소설 파일(txt/epub)을 일괄 처리하는 자동화 파이프라인.

- **입력**: 30개 폴더에 흩어진 소설 파일 (파일명 엉망, 메타데이터 없음)
- **출력**: 정규화된 파일명 + 메타데이터가 삽입된 EPUB 파일
- **운영**: 매일 약 200개 신규 파일 추가 처리, 최종 한 폴더로 통합

---

## 2. 언어/기술 스택: ✅ **Python 단일 스택** (확정)

### 결정 근거

| 판단 기준 | Python | Node.js |
|---|---|---|
| **기존 참조 코드** | ✅ NovelAIze-SSR, txt-to-epub-converter 전부 Python | ❌ 포팅 필요 |
| **EPUB 생성** | ✅ `EbookLib` (EPUB2/3 + 검증됨) | ❌ 직접 XML 조립 |
| **챕터 분할** | ✅ Splitter 클래스 그대로 재사용 가능 | ❌ 처음부터 구현 |
| **인코딩 감지** | ✅ `chardet` (UTF-8, EUC-KR, CP949) | ⚠️ 직접 구현 |
| **TUI** | ✅ `rich` (한글 폭 정확, 박스 안 비뚤어짐) | ⚠️ blessed (한글 폭 이슈) |
| **AI API** | ✅ `google-generativeai`, REST 호출 | ✅ 동일 |
| **배치 파일처리** | ✅ `pathlib`, `shutil`, `os` 네이티브 | ⚠️ 가능하나 덜 편함 |

### 기존 JS 코드는?
- 현재 리포(`Novel_Total_Processor`)의 JS는 **프로젝트 템플릿** (`init-project.js`, 워크플로우 스크립트)뿐
- 핵심 로직과 무관하므로 **JS를 완전히 제거하고 Python으로 재구성**
- PowerShell(`Novel_Title_Normalizer`)의 **로직과 프롬프트**만 Python으로 포팅

### 핵심 Python 패키지

```
# 핵심
ebooklib          — EPUB 생성 (EPUB2 호환, 모바일 안정)
chardet           — 인코딩 자동 감지
Pillow            — 표지 이미지 처리/리사이즈

# AI
google-generativeai — Gemini API (공식 SDK)
requests          — Perplexity API 호출 (REST)
tenacity          — API 재시도 (지수 백오프)

# 데이터
better-sqlite3 (또는 sqlite3 내장) — SQLite DB

# UI/CLI
rich              — Rich TUI (프로그레스바, 테이블, 라이브 갱신)
typer (또는 click) — CLI 명령어 파서

# 유틸
pyyaml            — 파일명 규칙 외부 설정
tqdm              — (rich에 통합 가능)
xxhash            — 초고속 파일 해시 (중복 감지)
pathlib           — 파일 경로 처리 (내장)
```

---

## 3. 데이터 저장: ✅ **SQLite + JSON 하이브리드** (확정)

### 역할 분리

| 저장소 | 용도 | 예시 |
|---|---|---|
| **SQLite** (`novels.db`) | 정규화된 메타데이터, 상태 관리, 중복 감지, 검색/필터 | 작품명, 작가, 장르, 화수, pipeline 상태 |
| **JSON 캐시** (`data/cache/`) | AI 원본 응답, 패턴 분석 결과, 디버깅/재가공용 | `ai_meta/{hash}.json`, `episode_pattern/{hash}.json` |
| **로그 파일** (`data/logs/`) | 처리 과정 상세 기록, 사후 분석용 | `2026-02-12.log`, `batch_daily_20260212.log` |

### SQLite 스키마 (Codex안 + Antigravity안 통합)

```sql
-- ============================================
-- 파일 테이블 (물리적 파일 1:1)
-- ============================================
CREATE TABLE files (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  file_path       TEXT NOT NULL UNIQUE,    -- 원본 전체 경로 (E:\소설\폴더\파일.txt)
  file_name       TEXT NOT NULL,           -- 원본 파일명
  file_ext        TEXT NOT NULL,           -- .txt / .epub
  file_size       INTEGER,                 -- 바이트
  file_hash       TEXT,                    -- XXHash (중복 감지)
  is_duplicate    INTEGER DEFAULT 0,       -- 1이면 중복 파일
  duplicate_of    INTEGER,                 -- 원본 file_id (중복 시)
  novel_id        INTEGER,                 -- 연결된 소설 ID
  created_at      TEXT DEFAULT (datetime('now','localtime')),
  FOREIGN KEY (novel_id) REFERENCES novels(id)
);

CREATE INDEX idx_files_hash ON files(file_hash);

-- ============================================
-- 소설 테이블 (논리적 작품 단위)
-- ============================================
CREATE TABLE novels (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  title           TEXT NOT NULL,           -- 소설 제목
  author          TEXT,                    -- 작가명
  genre           TEXT,                    -- 대표 장르 (퓨전판타지, 로맨스 등)
  tags            TEXT,                    -- JSON 배열: ["현대물","환생","성장물"]
  status          TEXT,                    -- 완결 / 연재 / 외전 등
  rating          REAL,                    -- ★ 점수 (0.0 ~ 5.0)
  cover_path      TEXT,                    -- 표지 이미지 로컬 경로
  cover_url       TEXT,                    -- 표지 이미지 원본 URL
  
  -- 화수 정보
  episode_range   TEXT,                    -- "1~230" 또는 복합 범위
  episode_detail  TEXT,                    -- JSON: 본편/외전/에필 상세
  
  -- 정규화된 파일명
  normalized_name TEXT,                    -- 규칙 적용 후 파일명
  
  -- EPUB 결과
  epub_path       TEXT,                    -- 생성된 EPUB 경로
  chapter_count   INTEGER,                 -- 총 챕터 수
  
  -- 메타데이터 캐시 참조
  meta_cache_path TEXT,                    -- data/cache/ai_meta/{hash}.json
  
  -- 추적
  created_at      TEXT DEFAULT (datetime('now','localtime')),
  updated_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================
-- 부가 도서 정보 (있으면 좋고 없어도 됨)
-- ============================================
CREATE TABLE novel_extra (
  novel_id        INTEGER PRIMARY KEY,
  isbn            TEXT,
  publisher       TEXT,
  publish_date    TEXT,
  description     TEXT,
  source_url      TEXT,                    -- AI 검색 출처
  raw_json_path   TEXT,                    -- 원본 응답 JSON 파일 경로
  FOREIGN KEY (novel_id) REFERENCES novels(id)
);

-- ============================================
-- 화수 패턴 (AI 분석 결과)
-- ============================================
CREATE TABLE episode_patterns (
  file_id         INTEGER PRIMARY KEY,
  pattern_regex   TEXT,                    -- 감지된 정규식
  detected_start  INTEGER,                -- 실제 시작화
  detected_end    INTEGER,                -- 실제 끝화
  confidence      REAL,                   -- 신뢰도 (0.0~1.0)
  pattern_json    TEXT,                    -- 상세 JSON 경로
  FOREIGN KEY (file_id) REFERENCES files(id)
);

-- ============================================
-- 파일명 변경 계획 (검수용)
-- ============================================
CREATE TABLE rename_plan (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id         INTEGER NOT NULL,
  old_name        TEXT NOT NULL,
  new_name        TEXT NOT NULL,
  approved        INTEGER DEFAULT 0,       -- 0=미검수, 1=승인, -1=거부
  applied         INTEGER DEFAULT 0,       -- 0=미적용, 1=적용완료
  applied_at      TEXT,
  FOREIGN KEY (file_id) REFERENCES files(id)
);

-- ============================================
-- 파이프라인 처리 상태
-- ============================================
CREATE TABLE processing_state (
  file_id         INTEGER PRIMARY KEY,
  stage0_indexed  INTEGER DEFAULT 0,       -- 인덱싱 완료
  stage1_meta     INTEGER DEFAULT 0,       -- 메타데이터 수집 완료
  stage2_episode  INTEGER DEFAULT 0,       -- 화수 검증 완료
  stage3_rename   INTEGER DEFAULT 0,       -- 파일명 계획 생성
  stage4_split    INTEGER DEFAULT 0,       -- 텍스트 전처리/분할
  stage5_epub     INTEGER DEFAULT 0,       -- EPUB 변환 완료
  last_error      TEXT,                    -- 마지막 에러 메시지
  last_stage      TEXT,                    -- 마지막 처리 단계
  updated_at      TEXT DEFAULT (datetime('now','localtime')),
  FOREIGN KEY (file_id) REFERENCES files(id)
);

-- ============================================
-- 배치 로그
-- ============================================
CREATE TABLE batch_logs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_name      TEXT,                    -- 'daily_2026-02-12' 등
  batch_type      TEXT,                    -- 'full' / 'daily'
  total_files     INTEGER,
  processed       INTEGER,
  success         INTEGER,
  failed          INTEGER,
  started_at      TEXT,
  finished_at     TEXT,
  duration_sec    INTEGER
);
```

---

## 4. 파이프라인 아키텍처: ✅ 7단계 (확정)

```
Stage 0: 초기 인덱싱 (파일 수집 + 해시 + 중복 감지)
    ↓
Stage 1: 메타데이터 수집 (Gemini/Perplexity API)
    ↓
Stage 2: 화수 검증 (파일 앞뒤 20KB → AI 분석)
    ↓
Stage 3: 파일명 계획 (규칙 적용 → 검수용 리스트 생성)
    ↓  ← 사용자 수동 검수 후 승인
Stage 4: 텍스트 전처리 (챕터 분할 구분자 삽입)
    ↓
Stage 5: EPUB 변환 (EbookLib + 메타데이터 + 표지)
    ↓
Stage 6: 통합 + 일일 배치 (최종 폴더 이동, 중복 정리)
```

### Stage 0: 초기 인덱싱
- 30개 폴더 재귀 스캔
- 확장자 필터: `.txt`, `.epub` (`.exe`, `.bat`, `.json` 등 제외)
- 512바이트 미만 파일 제외
- XXHash 계산 → 중복 감지 (`is_duplicate = 1`)
- 같은 소설 다른 화수 (예: 소설A 1~340화, 소설A 1~345화) 감지
- DB `files` 테이블 등록

### Stage 1: 메타데이터 수집
- **소스**: 기존 `Novel_Title_Normalizer`의 Gemini 프롬프트 **그대로 포팅**
  - 파일명에서 제목/작가/장르/태그/상태/화수 추출하는 상세 규칙 30+개 예제
  - `SystemPrompt` 전문 (387줄) 재사용
- **1차**: Gemini API (파일명 기반 메타데이터 추출)
- **2차**: Perplexity API (웹 검색으로 별점/표지/추가정보 보강)
- **처리 방식**: 10개씩 청크 묶어서 전송 (기존 `$ChunkSize = 10`)
- **Rate Limit**: 분당 60회 (증가 가능, 유료 사용자)
- **캐시**: `data/cache/ai_meta/{file_hash}.json` — 동일 파일 재조회 방지
- **결과**: `novels` 테이블 + `novel_extra` 테이블

### Stage 2: 화수 검증
- 파일 **앞 20KB + 뒤 20KB** 추출
- 인코딩 자동 감지 (`chardet`)
- AI에 전송 → 실제 화수 범위 확인
  - 예: "파일명엔 549~601이지만 실제로 1화부터 있음"
- 결과 패턴은 Stage 4에서 재사용
- **캐시**: `data/cache/episode_pattern/{file_hash}.json`
- **소스**: `NovelAIze-SSR`의 `pattern_analysis` 프롬프트 + `Sampler` 모듈 참고

### Stage 3: 파일명 계획 생성
- Stage 1, 2 결과를 조합하여 새 파일명 생성
- **규칙은 `rules.yml`에 외부 정의** (나중에 변경 가능)
- Windows 260자 제한 검사 + fallback 축약
- `rename_plan` 테이블에 저장
- **검수용 파일 출력**: `mapping_result_YYYYMMDD.txt`
  ```
  원본파일명   -----------------   새파일명
  ```
- **사용자가 메모장으로 열어서 확인** → 승인 후 실제 rename 실행
- **일괄 재생성 기능**: 규칙 변경 시 DB 기반으로 15000+개 파일명 일괄 재적용

### Stage 4: 텍스트 전처리 (챕터 분할)
- **소스**: `NovelAIze-SSR v3.0`의 핵심 로직 **그대로 포팅**
  - `Splitter` 클래스: Generator 기반 스트리밍 (메모리 효율적)
  - `PatternManager`: AI 적응형 패턴 탐지 (Multi-Stage Retry, 최대 5회)
  - `Sampler`: 파일 샘플링 (앞/중간/뒤)
  - Tail Detection: 에필로그/후기 잔존 감지 (50KB 이상 남으면 추가 탐색)
- 감지된 패턴으로 구분자 삽입
- 결과: 구분자가 삽입된 수정 txt 파일

### Stage 5: EPUB 변환
- **핵심 라이브러리**: `EbookLib` (Python)
  - **EPUB2 포맷** 생성 → 거의 모든 전자책 리더 호환 (킨들, 리디, 교보, Moon+ Reader 등)
  - 표지 이미지 삽입 (`Pillow`로 리사이즈)
  - `content.opf`에 메타데이터 최대한 삽입 (제목, 작가, 장르, 태그, 출판사, ISBN 등)
  - NCX 목차 자동 생성
- **CSS 스타일**: `txt-to-epub-converter`의 다看 스타일 CSS (382줄) 참고/포팅
  - 한글 폰트 스택, 반응형 디자인, 인쇄 최적화 포함
- **소스 참고 우선순위**:
  1. `txt-to-epub-converter` — 파서, CSS, 챕터 구조 (★ 주력)
  2. `ez-books` — DB 스키마, 메타데이터 구조 (참고)
  3. `txt2pub` — 사용 안 함 (너무 단순)

### Stage 6: 통합 + 일일 배치
- 완성된 EPUB을 최종 폴더로 이동
- 동일 소설 구버전 감지 → 최신 버전만 유지
- 배치 로그 기록
- 일일 200개 처리 → 마스터 폴더에 병합

---

## 5. 파일명 규칙: ✅ 기본형 확정

### 확정된 포맷

```
{제목}__{화수범위}_{상태}__★{별점}__{장르}__{작가}.{확장자}
```

### 실제 예시

```
평행차원에서_온_능력자__1~230_완결__★3.0__퓨전판타지__광수.txt

마탄의_사수__1~2126_완결_본편.1~1352_외전.1~746_에필.1~28__★4.2__무협판타지__작가명.epub

#따먹히는_순애_금태양__0~317_완결__★3.5__성인__작가명.txt
```

### 핵심 규칙
- 공백 → `_` (언더바)
- 필드 구분자: `__` (더블 언더바)
- 화수 구분자: `~` (예: `1~230`)
- 본편/외전/에필 구분: `.` (예: `외전.1~35`)
- 성인물: `#` 접두사
- 한자: 모두 삭제
- `[작가명]`, `(장르)` 등 메타태그: 삭제 후 적절한 필드로 분리
- `[AI번역]` 같은 태그: 보존
- **제목 길이 제한 없이 전체 유지** (사용자 요청)
- 260자 초과 시: 장르/작가명을 축약하는 fallback

### 규칙 변경 대응
- **모든 규칙은 `config/rules.yml`에 외부 정의**
- 규칙 변경 시 `python ntp.py reapply-names` 한 줄로 전체 일괄 재생성
- DB에 모든 메타데이터가 있으므로 언제든 새 포맷으로 변환 가능

---

## 6. EPUB 변환 전략: ✅ 확정

### 방식: `EbookLib` 라이브러리 사용 (직접 XML 조립 아님)

| 결정 사항 | 선택 | 이유 |
|---|---|---|
| EPUB 버전 | **EPUB2** | 거의 모든 기기/리더 호환 |
| 변환 라이브러리 | **EbookLib** | 검증된 Python 라이브러리, 코드 1줄로 챕터/표지/메타데이터 삽입 |
| CSS 스타일 | txt-to-epub-converter의 다看 스타일 참고 | 한글 폰트, 반응형, 인쇄 최적화 |
| 표지 이미지 | Stage 1에서 다운로드, Pillow로 리사이즈 | EPUB 내 삽입 |
| 메타데이터 | content.opf에 DB 정보 최대한 삽입 | 제목, 작가, 장르, 태그, ISBN 등 |

---

## 7. TUI (터미널 UI): ✅ 방향 확정

### `rich` 라이브러리 사용

**요구사항**:
- 박스가 비뚤비뚤하지 않아야 함 → `rich`는 한글 폭 계산이 정확
- 자세한 상황을 알 수 있도록 → `rich.live` + `rich.table`
- 로그 파일로 상세 출력 → `logging` 모듈 파일 핸들러

### UI 구성

```
╭─────────────────────────────────────────────────────────────╮
│ 📚 Novel Total Processor v1.0                    02:43:21  │
├─────────────────────────────────────────────────────────────┤
│ 현재 단계: Stage 1 — 메타데이터 수집                         │
│                                                             │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━ 58% ━━━━━━━━━━░░░░░░░░░░░░░░░ │
│                                                             │
│ 전체: 15,213  │ 완료: 8,823  │ 실패: 12  │ 남은: 6,378      │
│ API: Gemini 3 Flash   RPM: 58/60   큐 대기: 42             │
│                                                             │
│ ┌ 최근 처리 ────────────────────────────────────────────┐   │
│ │ ✅ 이혼_후_코인대박 → 퓨전판타지, ★3.8, 광수          │   │
│ │ ✅ 천하제일인의_소꿉친구 → 무협, ★4.2, 작가미상        │   │
│ │ ❌ 알수없는소설.txt → API 타임아웃 (재시도 2/5)        │   │
│ │ ⏳ 마탄의_사수... 처리 중                              │   │
│ └──────────────────────────────────────────────────────┘   │
│                                                             │
│ [P] 일시정지  [S] 건너뛰기  [Q] 종료      ETA: ~3h 12m     │
╰─────────────────────────────────────────────────────────────╯
```

### 로그 파일 출력
- **실시간 로그**: `data/logs/YYYY-MM-DD.log` (전 과정 상세 기록)
- **배치 요약**: `data/logs/batch_summary_YYYYMMDD.txt` (통계 + 실패 목록)
- 나중에 어떻게 진행되었는지 확인/분석 가능

---

## 8. 배치 처리 전략: ✅ 확정

### 대량 처리 (최초 15,000개)
- **단계별 일괄 처리** (한 소설씩 Stage 0~6을 하지 않음)
- Stage 0에서 15,000개 전체 → Stage 1에서 15,000개 전체 → ...
- API 호출 단계는 **며칠이 걸려도 상관없음** (사용자 확인)
- Rate Limit만 지키면 됨 (유료 사용자이므로 API 차단 걱정 없음)
- 중간에 멈춰도 DB에 상태 저장 → 재개 가능

### 일일 배치 (200개)
```
1. inbox 폴더에 새 파일 넣기
2. python ntp.py daily --source "E:\Downloads\오늘_소설"
3. Stage 0~5 자동 진행
4. 완성된 EPUB → 마스터 폴더로 이동
5. 원본은 archive 폴더로 이동
```

### 중복 처리
- 동일 해시 → 즉시 중복 표시 (is_duplicate)
- 동일 소설 다른 화수 → 최신(화수 많은) 버전만 유지

---

## 9. 프로젝트 디렉토리 구조: ✅ 확정

```
E:\DEVz\10_Novel_Total_Processor\
├── config/
│   ├── config.yml            — API 키, 모델명, RPM 제한 등
│   └── rules.yml             — 파일명 규칙 정의 (외부 변경 가능)
│
├── data/
│   ├── novels.db             — SQLite 메인 DB
│   ├── cache/
│   │   ├── ai_meta/          — {file_hash}.json (AI 메타 응답 원문)
│   │   └── episode_pattern/  — {file_hash}.json (화수 패턴 분석)
│   ├── covers/               — 표지 이미지 저장
│   ├── logs/                 — 처리 로그
│   └── temp/                 — 전처리 임시 파일
│
├── src/
│   ├── __init__.py
│   ├── main.py               — CLI 진입점 (typer)
│   ├── config.py             — 설정 로드/관리
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── schema.py         — SQLite 스키마 + 마이그레이션
│   │   └── repository.py     — DB CRUD 래퍼
│   │
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── stage0_indexer.py     — 파일 수집 + 해시 + 중복
│   │   ├── stage1_metadata.py    — AI 메타데이터 수집
│   │   ├── stage2_episode.py     — 화수 검증
│   │   ├── stage3_rename.py      — 파일명 계획 생성
│   │   ├── stage4_splitter.py    — 텍스트 전처리/분할
│   │   └── stage5_epub.py        — EPUB 변환
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── gemini_client.py      — Gemini API 래퍼
│   │   ├── perplexity_client.py  — Perplexity API 래퍼
│   │   ├── rate_limiter.py       — RPM 제한
│   │   └── prompts.py            — AI 프롬프트 관리
│   │
│   ├── epub/
│   │   ├── __init__.py
│   │   ├── builder.py            — EbookLib 기반 EPUB 생성
│   │   └── styles.py             — CSS 스타일 정의
│   │
│   ├── naming/
│   │   ├── __init__.py
│   │   ├── rule_engine.py        — 파일명 규칙 엔진
│   │   └── post_process.py       — 후처리 (불법문자 제거 등)
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   └── dashboard.py          — Rich TUI 대시보드
│   │
│   └── utils/
│       ├── __init__.py
│       ├── encoding.py           — 인코딩 감지/변환
│       ├── hash.py               — XXHash 파일 해시
│       └── file_utils.py         — 파일 유틸리티
│
├── pipelines/
│   ├── full_batch.py         — 전체 일괄 처리
│   ├── daily_batch.py        — 일일 배치
│   └── reapply_names.py      — 파일명 규칙 일괄 재적용
│
├── prompts.txt               — AI 프롬프트 (사용자 메모장으로 수정 가능)
├── requirements.txt
├── pyproject.toml
└── docs/
    ├── reference/            — 기존 참조 코드 (읽기 전용)
    └── 설계서/               — 이 문서
```

---

## 10. 기존 참조 코드 재사용 계획

### Novel_Title_Normalizer v1.2.4 (PowerShell)
| 재사용 대상 | 방법 |
|---|---|
| AI 프롬프트 (`$SystemPrompt`, 387줄) | **그대로** `prompts.txt`에 복사 |
| 파일명 정규화 규칙 30+개 예제 | `rules.yml` + 프롬프트에 반영 |
| 후처리 로직 (`Post-Process` 함수) | `naming/post_process.py`로 포팅 |
| 청크 처리 (10개씩 묶기) | `stage1_metadata.py`에 동일 구현 |
| 매핑 파일 생성/검수 흐름 | `stage3_rename.py`에 동일 구현 |

### NovelAIze-SSR v3.0 (Python)
| 재사용 대상 | 방법 |
|---|---|
| `Splitter` 클래스 (Generator 기반) | **거의 그대로** `stage4_splitter.py`에 포팅 |
| `PatternManager` (적응형 AI 패턴 탐지) | 동일 로직 포팅 |
| `Sampler` (파일 샘플링) | `stage2_episode.py`에 채택 |
| `RateLimiter` (분당 60회) | `ai/rate_limiter.py`에 포팅 |
| `pattern_analysis` 프롬프트 | `prompts.txt`에 추가 |
| `config.json` 구조 | `config/config.yml`에 반영 |

### txt-to-epub-converter (Python)
| 재사용 대상 | 방법 |
|---|---|
| `core.py` — EPUB 생성 흐름 | `epub/builder.py`에 참고/포팅 |
| `css.py` — 다看 스타일 CSS (382줄) | `epub/styles.py`에 채택 (한글 폰트 스택 포함) |
| `_read_txt_file` — chardet 인코딩 감지 | `utils/encoding.py`에 포팅 |
| `ParserConfig` — 챕터 감지 설정 | `config/rules.yml`에 반영 |
| `resume_state.py` — 중단/재개 | SQLite `processing_state`로 대체 (더 안정적) |

### ez-books (Rust)
| 재사용 대상 | 방법 |
|---|---|
| DB 스키마 구조 (books, book_subjects) | SQLite 스키마 설계 참고 |
| 메타데이터 필드 (ISBN, publisher 등) | `novel_extra` 테이블에 반영 |
| OpenLibrary 연동 아이디어 | (선택) 추후 추가 가능 |

### txt2pub (HTML)
- **사용 안 함** (클라이언트 사이드 단일 파일, 기능 너무 단순)

---

## 11. CLI 명령어 구조

```bash
# 전체 파이프라인 실행 (최초 대량 처리)
python ntp.py run --source "E:\소설폴더들" --output "E:\소설_완성"

# 일일 배치
python ntp.py daily --source "E:\Downloads\오늘" --output "E:\소설_완성"

# 특정 단계만 실행 (중단 후 재개)
python ntp.py stage --step 1 --resume

# 상태 확인
python ntp.py status

# 파일명 매핑 검토
python ntp.py review

# 파일명 규칙 변경 후 일괄 재적용
python ntp.py reapply-names

# 중복 파일 정리
python ntp.py deduplicate
```

---

# Part 2: 미확정 사항 (결정 필요)

---

## ❓ 1. 기존 리포 처리

**선택지**:
- **A**: `Novel_Total_Processor` 리포 내용을 싹 비우고 Python으로 재구성
- **B**: 새 리포 생성 (예: `Novel_Total_Processor_PY`)

**Codex 의견**: 새 리포 분리 권장  
**Antigravity 의견**: 기존 리포를 비우는 게 간단 (이미 폴더 구조/docs/reference가 있으므로)

---

## ❓ 2. 파일명 구분자 최종 확정

현재 합의: `__` (더블 언더바)

```
제목__화수_상태__★별점__장르__작가.ext
```

**추가 고려**: 파일명에서 `__`가 시각적으로 좀 길어 보일 수 있음. 이대로 갈지, 다른 구분자를 쓸지?

---

## ❓ 3. Perplexity API 활용 범위

- 현재 Perplexity API 키를 갖고 계신 것은 확인
- **질문**: Perplexity는 메타데이터 검색의 **보조**로만 쓸지, **주력**으로 쓸지?
  - 보조: Gemini로 기본 추출 → Perplexity로 별점/표지만 보강
  - 주력: 파일명과 함께 웹 검색을 시켜서 더 정확한 정보 확보

---

## ❓ 4. 기존 Novel_Title_Normalizer AI 프롬프트 포팅 여부

`Novel_Title_Normalizer v1.2.4`의 SystemPrompt (387줄)에는:
- 파일명 정규화의 **모든 규칙과 예제** 30+개가 포함
- 이걸 **그대로 가져와서** Stage 1/3에서 쓸지?
- 아니면 새로 더 정교하게 만들지?

**추천**: 그대로 가져오되, Stage별로 분리 (메타추출용 / 이름생성용)

---

## ❓ 5. 구현 우선순위

전체를 한 번에 다 만들 수 없으므로, 어떤 순서로 만들까?

**추천 순서**:
1. **Phase A (기반)**: DB 스키마 + config + Stage 0 (인덱싱)
2. **Phase B (핵심)**: Stage 1 (메타수집) + Stage 3 (파일명) — 이것만으로도 파일명 정리 가능
3. **Phase C (분석)**: Stage 2 (화수 검증)
4. **Phase D (변환)**: Stage 4 (분할) + Stage 5 (EPUB)
5. **Phase E (통합)**: Stage 6 (배치) + TUI + 일일배치

---

# Part 3: 위험 요소 & 대비책

| 위험 | 대비 |
|---|---|
| AI 결과가 부정확함 | Stage 3에서 **사용자 수동 검수** 단계 필수 |
| API 분당 제한 | `tenacity` + `rate_limiter.py`로 자동 조절 |
| 파일명 260자 초과 | 장르/작가 축약 fallback + 경고 로그 |
| 인코딩 깨짐 | `chardet` 다중 인코딩 시도 + `errors='replace'` |
| 대용량 파일 메모리 | Generator 기반 스트리밍 (NovalAIze-SSR 방식) |
| 중간에 멈춤 | SQLite `processing_state`로 정확한 지점에서 재개 |
| 파일명 규칙 변경 | `rules.yml` 외부화 + `reapply-names` 일괄 재적용 |

---

# Part 4: 참조 소스 분석 요약

| 프로젝트 | 언어 | 코드량 | 핵심 가치 | 채택 수준 |
|---|---|---|---|---|
| Novel_Title_Normalizer v1.2.4 | PowerShell | 813줄 | AI 프롬프트, 파일명 규칙, 청크 처리 | ★★★★★ 로직 전면 포팅 |
| NovelAIze-SSR v3.0 | Python | 23개 파일 | 챕터 분할, 패턴 탐지, Rate Limiter | ★★★★★ 핵심 모듈 재사용 |
| txt-to-epub-converter | Python | 11개 파일 | EPUB 생성, CSS, 인코딩 감지 | ★★★★☆ 빌더+CSS 참고 |
| ez-books | Rust | 15개 파일 | DB 스키마, 메타데이터 구조 | ★★☆☆☆ 구조만 참고 |
| txt2pub | HTML | 1개 파일 | — | ☆☆☆☆☆ 사용 안 함 |
