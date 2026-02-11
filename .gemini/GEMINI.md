# 무조건 지켜야 하는 최중요 규칙

- 사용자의 말을 너무 과대 해석하거나 임의로 편하게 해석 해서 임의로 코드를 작성하거나 작업을 진행하지 않는다
- 사용자가 말한것, 시키는 작업을 반드시 먼저 설명을 하고 승인후에 작업을 시작한다
- 사용자의 명령이 애매하거나 모호하면 반드시 사용자에게 다시 질문과 설명을 하고 승인을 받아야 한다

# 🛠️ Stealth-Clicker 워크스페이스 규칙

> **이 파일은 프로젝트 생성 시 자동으로 배치됩니다.**

---

## 📋 필수 읽기 문서

| 순서 | 문서 | 설명 |
|:---:|:---|:---|
| 1 | `.agent/constitution.md` | 핵심 규칙 (불변) |
| 2 | `docs/ISSUES.md` | GitHub Issue 미러 |
| 3 | `docs/HANDOVER.md` | 세션 인계 (있으면) |

---

## 🔧 프로젝트 설정

| 항목 | 값 |
|:---|:---|
| 언어 | Node.js (ES Module) |
| 패키지 매니저 | npm |
| 테스트 | `npm test` |
| 빌드 | `npm run build` (해당 시) |

---

## 📂 폴더 구조

```
프로젝트/
├── .agent/                    # AI 에이전트 규칙
│   ├── constitution.md       # 핵심 규칙
│   └── workflows/            # 워크플로우
├── .gemini/                   # 워크스페이스 설정
│   └── GEMINI.md             # 이 파일
├── docs/                      # 문서
│   ├── ISSUES.md             # GitHub Issue 미러
│   ├── HANDOVER.md           # 세션 인계
│   ├── SHELL_GUIDE.md        # 터미널 가이드
│   └── reference/            # 참고 문서 (읽기 전용)
├── scripts/                   # 자동화 스크립트
└── src/                       # 소스 코드
```

---

## 🚀 워크플로우

> [!CAUTION]
> **새 작업 시작 시 반드시 이 순서대로!**

### 필수 순서

1. **작업 시작**: `npm run start-task -- <type> "제목"`
   - type: bug, feat, enhance
   - 이슈 번호 받음 (#N)

2. **이슈 번호 기록**: task.md 또는 문서에 기록

3. **작업 진행**: 코드 작성, 테스트 등

4. **작업 완료**: `npm run finish -- "메시지 (#N)"`

5. **핸드오버**: `/handover` (스텝 250~350 시)

### 예시

```bash
# 1. 작업 시작
npm run start-task -- feat "파일 다운로드"
# → 이슈 #35 생성

# 2. 작업 완료
npm run finish -- "feat: 파일 다운로드 (#35) [MOD]"
# → 자동 커밋 + 푸시 + 동기화
```

---

## ⚠️ AI 에이전트 필수 체크리스트

> [!CAUTION]
> **AI는 매번 아래 체크리스트를 확인!**

### 작업 시작 시

```
task_boundary를 호출했나?
└→ YES: **즉시 다음 단계에서 npm run start-task 실행!**
└→ NO: 계속 진행

implementation_plan.md를 작성했나?
└→ YES: notify_user 후 사용자 승인 대기
└→ 승인 받음: **즉시 start-task 실행 후 작업 시작!**
```

### 작업 중간

```
스텝 수를 체크했나?
└→ 250 이상: HANDOVER.md 업데이트 경고
└→ 350 도달: 즉시 작업 중단 + 핸드오버!
```

### 작업 완료 시

```
npm run finish 실행했나?
└→ YES: 이슈 번호 (#N) 포함 확인
└→ NO: **finish-task 없이 끝내면 안 됨!**
```
