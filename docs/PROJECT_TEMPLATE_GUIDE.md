# 📚 프로젝트 템플릿 & 워크플로우 가이드

> **버전**: 1.1 (2026-01-07)
> **위치**: `E:\DEVz\_templates\project-template\`

---

## 🚀 새 프로젝트 시작하기

### 1단계: 템플릿 적용

```bash
# 새 프로젝트 폴더로 이동
cd E:\DEVz\새프로젝트

# 템플릿 초기화 (한 줄 명령!)
node E:\DEVz\_templates\project-template\init-project.js "프로젝트명"
```

### 2단계: Git & GitHub 설정

```bash
# Git 초기화
git init

# GitHub 저장소 생성 + 연결
gh repo create 프로젝트명 --public --source=. --remote=origin

# 첫 커밋
git add .
git commit -m "chore: 프로젝트 초기 설정 [N/A]"
git push -u origin master
```

### 3단계: 첫 번째 이슈 생성

```bash
npm run start-task -- feat "첫 번째 기능"
```

---

## 📁 생성되는 폴더 구조

```
프로젝트/
├── .agent/
│   ├── constitution.md       # 핵심 규칙 (AI 필독!)
│   └── workflows/
│       ├── start-task.md     # 작업 시작 가이드
│       ├── finish-task.md    # 작업 완료 가이드
│       └── handover.md       # 세션 인계 가이드
├── .gemini/
│   └── GEMINI.md             # 워크스페이스 규칙
├── docs/
│   ├── ISSUES.md             # GitHub Issue 미러 (자동 동기화)
│   └── SHELL_GUIDE.md        # 터미널 먹통 방지 가이드
├── scripts/
│   ├── start-task.js         # 이슈 생성 스크립트
│   ├── finish-task.js        # 커밋/push 스크립트
│   ├── sync-issues.js        # 이슈 동기화 스크립트
│   └── test_sanity.js        # 기본 테스트
├── src/                       # 소스 코드
└── package.json
```

---

## 🔄 일일 워크플로우

### 작업 시작

```bash
# 이슈 먼저 생성!
npm run start-task -- <type> "제목"

# type: bug, feat, enhance, fix, refactor, chore, docs, style, test
```

**자동으로 되는 것:**

- GitHub Issue 생성 (상세 템플릿 포함)
- `docs/ISSUES.md` 동기화

### 작업 완료

```bash
npm run finish -- "type: 메시지 (#N)"

# 예시:
npm run finish -- "feat: 로그인 기능 구현 (#1) [MOD]"
npm run finish -- "fix: 버그 수정 (Closes #5) [N/A]"
```

**자동으로 되는 것:**

1. 이슈 번호 확인 (없으면 **차단!**)
2. **이슈 내용 검증** (템플릿 그대로면 차단!) **[신규]**
3. 모듈화 태그 확인 (src 수정 시)
4. `npm test` 실행
5. `git add . && commit && push`
6. `docs/ISSUES.md` 동기화

### 커밋 메시지 규칙

| 키워드 | 효과 |
|:---|:---|
| `#N` | 이슈 참조 (열린 상태 유지) |
| `Closes #N` | 이슈 자동 Close |
| `[MOD]` | 모듈화 완료 |
| `[RAW]` | 의도적으로 모듈화 안 함 |
| `[N/A]` | 해당 없음 |

---

## 🔁 세션 핸드오버

**트리거**: 스텝 250~350 도달 또는 `/handover` 명령

## 2. 작성 방법 (스냅샷 + 아카이브)

1. **아카이브**: 기존 `docs/HANDOVER.md`를 `docs/history/session_YYYYMMDD.md`로 이동합니다.
2. **새로 작성**: `docs/HANDOVER.md`를 **백지 상태**에서 새로 작성합니다.

### 템플릿

```markdown
# 🔄 세션 핸드오버

## 📌 [최신] 세션 N (YYYY-MM-DD)

### ✅ 완료된 작업
1. 작업 1
2. 작업 2

### 🚧 진행 중 / 남은 작업
- [ ] 작업 A (이슈 #10)
- [ ] 작업 B

### ⚠️ 주의사항 / 메모
- (다음 세션이 꼭 알아야 할 내용)
```

## 3. 필수 확인 사항

- `task_boundary`의 TaskStatus가 'Completed'인지 확인.
- `npm run finish`가 성공적으로 실행되었는지 확인.
- `docs/history/`에 이전 기록이 안전하게 저장되었는지 확인.

---

## ⚠️ 핵심 규칙 요약

| 규칙 | 설명 |
|:---|:---|
| **이슈 먼저** | 코드 수정 전 이슈 생성/확인 |
| **이슈 번호 필수** | 커밋 시 `#N` 없으면 차단 |
| **이슈 상세 작성** | **고등학생도 이해할 수 있는 수준**으로 상세 작성 필수 (검증함) |
| **gh 명령 금지** | 항상 Node.js 스크립트로 사용 (먹통 방지) |
| **핸드오버** | **스냅샷 + 아카이브** 방식 (덮어쓰기 허용, 이전 기록은 `docs/history/`로 이동) |

---

## 🛠️ 스크립트 명령어 요약

```bash
# 작업 시작 (이슈 생성)
npm run start-task -- <type> "제목"

# 작업 완료 (커밋 + push)
npm run finish -- "메시지 (#N)"

# 이슈 동기화 (수동)
npm run sync-issues

# 테스트 실행
npm test
```

---

## 📝 이슈 작성 템플릿

```markdown
## 🎓 배경 지식 (Context)
> 이 작업이 왜 필요한지, 관련된 기본 개념은 무엇인지, **개발을 처음 배우는 고등학생에게 설명하듯이** 상세하게 작성하세요.
> (예: "로그인 기능이란 사용자가 누구인지 확인하는 절차입니다. 현재는 이 기능이 없어서...")

## 🎯 목표 (Goal)
> 이 작업을 통해 달성하고자 하는 것이 무엇인지 구체적으로 설명하세요.
> (예: "사용자가 아이디/비번을 입력하고 로그인 버튼을 누르면 메인 페이지로 이동해야 합니다.")

## 🛠️ 기술적 계획 (Technical Plan)
> 어떤 파일을 어떻게 수정할 것인지 상세히 적으세요.
> - **수정할 파일**: `src/auth/Login.js`
> - **변경 내용**:
>   1. `checkLogin` 함수 내부에 유효성 검사 로직 추가
>   2. API 호출 에러 처리 추가

## ✅ 완료 조건 (Definition of Done)
- [ ] 조건 1
- [ ] 조건 2

## 📝 진행 기록
| 날짜 | 내용 |
|:---|:---|
| 2026-01-02 | 이슈 생성 |
```

---

> **다음 프로젝트에서**: 이 문서와 `init-project.js`만 있으면 바로 시작!
