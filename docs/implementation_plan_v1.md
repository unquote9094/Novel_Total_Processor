# Novel Total Processor — 기술 제안서 & 아키텍처 설계

> 15,000개+ 소설 파일을 일괄 처리하여 메타데이터 수집 → 파일명 정규화 → 챕터 분할 → EPUB 변환까지 자동화하는 파이프라인

---

## 1. 언어 선택: **Node.js + TypeScript**

### 왜 Node.js인가?

| 비교 항목 | Node.js (TypeScript) | Python |
|---|---|---|
| **기존 프로젝트 구조** | ✅ 이미 `package.json` ESM 기반 | ❌ 별도 환경 필요 |
| **대량 파일 I/O** | ✅ 비동기 I/O가 핵심 강점 | ⚠️ asyncio 필요 |
| **SQLite 성능** | ✅ `better-sqlite3` (동기, C++ 바인딩, 매우 빠름) | ⚠️ sqlite3 모듈 |
| **TUI (터미널 UI)** | ✅ `blessed`, `ink` (React 기반) — 매우 강력 | ⚠️ `rich` (좋지만 구조화 어려움) |
| **EPUB 생성** | ✅ `archiver`(zip) + XML 직접 생성 가능 | ✅ `EbookLib` 성숙 |
| **API 호출** | ✅ `fetch` 네이티브 (Node 18+) | ✅ `requests` |
| **유지보수** | ✅ 한 언어로 전체 통일 | ❌ PS + Python + JS 혼합 유지 |
| **타입 안전성** | ✅ TypeScript 타입 체크 | ⚠️ 타입 힌트(선택적) |

> 기존 Python/PowerShell 코드의 **로직**만 Node.js로 포팅합니다. 코드를 그대로 가져오는 게 아니라, 검증된 알고리즘과 규칙만 차용합니다.

### 핵심 npm 패키지

```
better-sqlite3    — SQLite (동기, 빠름, 안정적)
archiver          — ZIP 생성 (EPUB = ZIP)
xml2js            — XML 파싱/생성
fast-glob         — 초고속 파일 탐색
chardet / iconv-lite — 한글 인코딩 감지/변환
p-limit           — 동시성 제한 (API 호출)
blessed / blessed-contrib — Rich TUI
chalk             — 터미널 색상
xxhash-wasm       — 초고속 파일 해시 (중복 감지)
sharp             — 이미지 리사이즈 (표지)
```

---

## 2. 데이터베이스: **SQLite**

### 왜 SQLite인가?

15,000개 파일의 처리 상태를 메모리나 JSON으로 관리하면:
- 중간에 멈추면 **처음부터 다시 해야** 함
- 어디까지 했는지 **추적 불가**
- 중복 파일 **감지 불가**

SQLite를 쓰면:
- ✅ **중단/재개** — 전원이 꺼져도 DB에 상태가 남음
- ✅ **진행률 추적** — `SELECT COUNT(*) WHERE status = 'CONVERTED'` 한 줄로 확인
- ✅ **중복 감지** — `file_hash` 컬럼으로 즉시 판별
- ✅ **검색/필터** — 장르별, 작가별, 상태별 조회
- ✅ **단일 파일** — `novels.db` 하나로 모든 데이터 관리

### DB 스키마 (초안)

```sql
-- 소설 파일 테이블 (핵심)
CREATE TABLE novels (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  original_path TEXT NOT NULL,
  original_name TEXT NOT NULL,
  normalized_name TEXT,
  file_hash     TEXT,
  file_size     INTEGER,
  file_ext      TEXT,
  
  -- 메타데이터 (AI 검색 결과)
  title         TEXT,
  author        TEXT,
  genre         TEXT,
  tags          TEXT,
  status_info   TEXT,
  rating        REAL,
  cover_path    TEXT,
  
  -- 화수 정보 (콘텐츠 분석 결과)
  episode_start INTEGER,
  episode_end   INTEGER,
  episode_info  TEXT,
  
  -- 파이프라인 상태
  pipeline_status TEXT DEFAULT 'DISCOVERED',
  
  -- EPUB 관련
  epub_path     TEXT,
  chapter_count INTEGER,
  
  -- 추적
  error_log     TEXT,
  created_at    TEXT DEFAULT (datetime('now','localtime')),
  updated_at    TEXT DEFAULT (datetime('now','localtime')),
  
  UNIQUE(file_hash)
);

-- 부가 도서 정보
CREATE TABLE novel_metadata_extra (
  novel_id      INTEGER PRIMARY KEY,
  isbn          TEXT,
  publisher     TEXT,
  publish_date  TEXT,
  description   TEXT,
  source_url    TEXT,
  raw_response  TEXT,
  FOREIGN KEY (novel_id) REFERENCES novels(id)
);

-- 처리 로그
CREATE TABLE batch_logs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_name    TEXT,
  total_files   INTEGER,
  processed     INTEGER,
  success       INTEGER,
  failed        INTEGER,
  started_at    TEXT,
  finished_at   TEXT
);
```

---

## 3. 파이프라인 아키텍처

### Phase 1: Discovery (폴더 스캔)
- 30개 폴더를 재귀 탐색
- 파일별 XXHash 계산 → 중복 즉시 감지
- 512바이트 미만 파일 제외
- DB에 `DISCOVERED` 상태로 등록

### Phase 2: Metadata Fetch (AI 검색)
- **1차: Gemini API** — 파일명으로 제목/작가/장르/태그/상태 추출
- **2차: Perplexity API** — 웹 검색으로 별점/표지이미지/추가정보 보강
- 10개씩 청크로 묶어서 전송
- Rate Limiter: 분당 60회 제한

### Phase 3: Content Analysis (화수 파악)
- 파일 **앞 20KB + 뒤 20KB** 읽기
- 인코딩 자동 감지 (UTF-8, EUC-KR, CP949 등)
- AI에 전송하여 **실제 시작화/끝화** 파악

### Phase 4: Rename (파일명 정규화)
- 기존 PowerShell `Novel_Title_Normalizer v1.2.4`의 규칙을 **그대로** 포팅
- Phase 2, 3의 결과를 반영하여 완전한 파일명 생성
- 매핑 파일 생성 → 사용자 검토 → 적용

### Phase 5: Chapter Split (챕터 분할)
- 기존 `NovelAIze-SSR v3.0`의 로직 포팅
- Multi-Stage Adaptive Retry (최대 5회)
- Tail Detection (에필로그/후기 감지)
- 구분자 삽입 후 저장

### Phase 6: EPUB Build (EPUB 변환)
- **txt-to-epub-converter**의 구조를 주로 참고
- EPUB 직접 생성 (EPUB = ZIP + XML + XHTML)
- 표지 이미지 삽입, CSS 스타일링

### Phase 7: Consolidation (통합)
- 완성된 EPUB을 최종 폴더로 이동
- 동일 소설의 구버전 감지/교체
- 일일 배치 결과 병합

---

## 4. 배치 처리 전략

### 대량 처리 (15,000개)
- Phase별 순차 일괄 처리
- API 호출 단계는 밤에 돌려두기 적합

### 일일 배치 (200개)
- `node ntp.js --daily E:\Downloads\novels_today`
- 이미 DB에 등록된 파일(해시 일치)은 자동 건너뜀

---

## 5. EPUB 변환기 선택

| 프로젝트 | 언어 | 채택 |
|---|---|---|
| **txt-to-epub-converter** | Python | ✅ 로직 주력 참고 |
| **ez-books** | Rust | ✅ DB/메타데이터 구조 참고 |
| **txt2pub** | HTML | ❌ 사용 안 함 |

---

## 6. 프로젝트 디렉토리 구조

```
src/
├── index.ts              — CLI 진입점
├── config.ts             — 설정 관리
├── db/
│   ├── schema.ts         — SQLite 스키마
│   └── repository.ts     — DB CRUD
├── pipeline/
│   ├── orchestrator.ts   — 파이프라인 컨트롤러
│   ├── discovery.ts      — Phase 1
│   ├── metadata.ts       — Phase 2
│   ├── analyzer.ts       — Phase 3
│   ├── renamer.ts        — Phase 4
│   ├── splitter.ts       — Phase 5
│   ├── epub-builder.ts   — Phase 6
│   └── consolidator.ts   — Phase 7
├── ai/
│   ├── gemini-client.ts
│   ├── perplexity-client.ts
│   ├── rate-limiter.ts
│   └── prompts.ts
├── epub/
│   ├── builder.ts
│   ├── templates.ts
│   └── styles.ts
├── ui/
│   └── dashboard.ts      — blessed TUI
└── utils/
    ├── encoding.ts
    ├── hash.ts
    └── filename.ts
```

---

## 7. 실행 명령어

```bash
node ntp.js run --source "E:\소설들" --output "E:\소설_완성"
node ntp.js daily --source "E:\Downloads\오늘" --output "E:\소설_완성"
node ntp.js phase --step 2 --resume
node ntp.js status
node ntp.js review
```
