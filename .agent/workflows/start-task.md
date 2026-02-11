---
description: 새로운 작업 시작 시 GitHub 이슈 생성
---

# 📌 START-TASK

> **목적**: 작업 시작 전 GitHub 이슈 생성 → 나중에 추적 가능

---

## 언제 사용?

- 새로운 기능 개발 시작할 때
- 버그 수정 시작할 때
- 기존 코드 개선할 때

## 실행 방법

```bash
npm run start-task -- <type> "제목"
```

### 타입별 예시

| Type | 설명 | 예시 |
|:---|:---|:---|
| `bug` | 버그 수정 | `npm run start-task -- bug "첫 클릭 안됨"` |
| `feat` | 새 기능 | `npm run start-task -- feat "파일 다운로드"` |
| `enhance` | 개선 | `npm run start-task -- enhance "대기시간 랜덤화"` |
| `refactor` | 리팩토링 | `npm run start-task -- refactor "Login.js 구조 개선"` |
| `chore` | 관리/빌드 | `npm run start-task -- chore "npm 패키지 업데이트"` |
| `docs` | 문서 | `npm run start-task -- docs "README 수정"` |
| `style` | 스타일 | `npm run start-task -- style "세미콜론 포맷팅"` |
| `test` | 테스트 | `npm run start-task -- test "로그인 테스트 추가"` |

---

## 이슈 작성 시 필수 내용

> [!IMPORTANT]
> 나중에 봐도, 다른 사람이 봐도 이해할 수 있게!

### 1. 이슈 템플릿 (자동 생성됨)

> [!IMPORTANT]
> **개발을 처음 배우는 고등학생에게 설명하듯이 상세하게 작성하세요.**

```markdown
## 🎓 배경 지식 (Context)
> "로그인이란 사용자를 식별하는 과정입니다..." (친절한 설명)

## 🎯 목표 (Goal)
> "메인 페이지의 로그인 버튼을 활성화합니다."

## 🛠️ 기술적 계획 (Technical Plan)
> - `src/Login.js`: 유효성 검사 로직 추가

## ✅ 완료 조건 (Definition of Done)
- [ ] 테스트 통과
```

### 2. 작성 원칙

1. **친절함**: 전문 용어 남발 금지. 문맥(Context) 설명 필수.
2. **구체성**: "버그 수정" (X) -> "로그인 버튼 클릭 시 404 에러 수정" (O)
3. **계획성**: 어떤 파일을 어떻게 고칠지 미리 계획.

### 3. 관련 파일

```markdown
- `src/actions/MineGame.js` - 채굴 로직
- `src/core/HumanMouse.js` - 마우스 클릭
```

### 4. 체크리스트

```markdown
- [ ] 원인 분석
- [ ] 코드 수정
- [ ] 테스트
```

---

## 자동으로 되는 것

1. GitHub Issue 생성 (템플릿 적용)
2. `docs/ISSUES.md` 자동 동기화
3. 이슈 번호 발급 (#N)

---

## 작업 완료 후

```bash
npm run finish -- "fix: 첫 클릭 버그 수정 (#N) [MOD]"
```

> `#N`은 이슈 번호로 교체!
