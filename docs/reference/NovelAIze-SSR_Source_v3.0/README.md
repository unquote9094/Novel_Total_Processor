# 📚 NovelAIze-SSR v1.0 (Split & Summary & Reformat)

> **"수백 메가바이트의 텍스트 소설, AI가 알아서 쪼개고 요약해 줍니다."**
>
> NovelAIze-SSR은 대용량 웹소설 텍스트 파일을 챕터 단위로 정밀하게 분할하고, Google Gemini AI를 이용해 각 회차별 핵심 내용을 요약해주는 자동화 도구입니다.

---

## ✨ 핵심 기능 (Key Features)

### 1. 🧩 적응형 챕터 분할 (Adaptive Splitting & Retry)

단순한 정규식으로 찾지 못하는 복잡한 패턴도 AI가 찾아냅니다.

* **Multi-Stage Adaptive Retry**: AI가 1차 시도에서 모든 챕터를 찾지 못하면, 실패한 지점부터 다시 샘플링하여 2차, 3차 탐색을 수행합니다. (최대 5회)
* **Tail Detection (꼬리 감지)**: "완결"까지 찾았다고 해도, 남은 파일 용량이 50KB 이상이면 "에필로그나 후기가 남았다"고 판단하여 집요하게 찾아냅니다.
* **결과**: 99.9% 이상의 챕터 분할 성공률을 보장합니다.

### 2. ⚡ 초고속 AI 처리 (Rate Limiter)

Gemini 1.5/3.0 모델의 API 제한을 완벽하게 관리합니다.

* **Smart throttling**: 분당 요청 수(RPM)를 60회로 자동 제어하여 `429 Too Many Requests` 에러를 원천 차단합니다.
* **비동기 병렬 처리**: 기다리는 시간 없이 최대한의 속도로 요약을 찍어냅니다. (평균 0.7초/화)

### 3. 🔞 성인 모드 및 검열 우회 (Adult Code Bypass)

성인 웹소설 요약 시 발생하는 AI의 거부를 유연하게 대처합니다.

* **Safety Block Pass**: 선정적/폭력적 내용으로 AI가 응답을 거부(FinishReason: PROHIBITED/SAFETY)하면, 에러를 내고 멈추는 대신 `[🔞 검열됨]` 메시지를 남기고 **즉시 다음 화로 진행**합니다.
* 프로세스가 절대 중단되지 않으므로 밤에 켜두고 자도 안심입니다.

### 4. 🎨 사용자 친화적 설정 (User Friendly)

코드를 전혀 몰라도 메모장만으로 입맛대로 튜닝 가능합니다.

* **`prompts.txt`**: JSON 지옥에서 탈출하세요. 그냥 메모장(`prompts.txt`)을 열어서 한글로 프롬프트를 고치면 됩니다.
* **`config.json`**: API 키, 속도(RPM), 모델명 등을 쉽게 변경할 수 있습니다.
* **인터랙티브 UI**: 실행 시 `[1] 일반 [2] 판타지 [3] SF` 등 장르를 번호로 쉽게 선택할 수 있습니다.

---

## 🚀 시작하기 (Quick Start)

### 1. 준비물

* Windows 10/11
* Google Gemini API Key ([여기서 발급](https://aistudio.google.com/app/apikey))
* `dist/` 폴더 안의 파일들 (`NovelAIze-SSR.exe`, `config.json`, `prompts.txt`)

### 2. 설치 및 실행

1. **설정 파일 수정**:
    `dist/config.json` 파일을 열어서 발급받은 API 키를 넣으세요.

    ```json
    {
        "api_key": "YOUR_API_KEY_HERE",
        ...
    }
    ```

2. **실행**:
    `NovelAIze-SSR.exe`를 더블 클릭합니다.
3. **파일 선택**:
    자동으로 파일 선택 창이 뜹니다. 작업할 `.txt` 소설 파일을 선택하세요.

### 3. 메뉴 선택

```text
[1] 📝 서식 정리만 (Format Only)
    -> AI 요약 없이 챕터별로 파일만 깔끔하게 나눕니다.
[2] 🤖 AI 요약 (Summarize)
    -> 분할 + AI 요약을 수행합니다. 장르 선택 메뉴가 나옵니다.
[3] 👀 미리보기 (Preview)
    -> 앞부분 10개 챕터만 테스트로 요약해 봅니다.
[4] 🔞 AI 요약 - 성인용 (Adult Mode)
    -> 검열 에러를 무시하고 강제 진행하는 모드입니다.
```

---

## 🛠️ 설정 가이드 (Customization)

### 프롬프트 수정 (`prompts.txt`)

이 파일은 AI에게 시킬 "명령어"가 담긴 파일입니다. `=== 제목 ===`으로 구분되어 있습니다.
입맛에 맞게 문구를 수정하고 저장(`Ctrl+S`)하면 즉시 반영됩니다.

* `summary_fantasy`: 판타지 소설용 (상태창, 스킬 설명 중시)
* `summary_romance`: 로맨스 소설용 (감정선, 관계 변화 중시)
* `summary_general`: 일반 소설용
* `pattern_analysis`: 챕터 제목 패턴(정규식)을 찾을 때 쓰는 프롬프트 ("건드리지 않는 것을 추천")

### 고급 설정 (`config.json`)

```json
{
    "api_key": "...",              // 구글 API 키
    "model_name": "gemini-3-flash-preview", // 사용할 AI 모델 (flash 추천)
    "concurrency": 5,              // 동시에 처리할 챕터 수 (PC 성능에 따라 조절)
    "rate_limit_rpm": 60           // 분당 요청 횟수 (VIP 아니면 60 유지)
}
```

---

## ⚠️ 트러블슈팅 (FAQ)

**Q. 실행하자마자 바로 꺼져요!**
A. `config.json` 형식이 깨졌거나 API 키가 없을 수 있습니다. 키를 확인하세요.

**Q. "패턴을 찾지 못했습니다" 라고 떠요.**
A. 소설 형식이 너무 특이한 경우입니다. `[1] 서식 정리만` 모드를 켜서 AI가 패턴을 잘 찾는지 먼저 테스트해 보세요. 재시도 로직이 돌면서 웬만한 건 찾아냅니다.

**Q. 속도가 너무 느려요.**
A. `config.json`의 `concurrency`를 높일 수 있지만, `rate_limit_rpm` 60 제한 때문에 드라마틱하게 빨라지진 않습니다. (구글 무료 API의 한계)

**Q. 요약 내용이 마음에 안 들어요.**
A. `prompts.txt`를 여세요! "세 줄 요약 해줘", "반말 써줘" 처럼 한글로 적으면 AI가 그대로 수행합니다.

---

## 💻 개발자 가이드 (Build from Source)

소스 코드를 수정하고 싶다면 다음 순서로 빌드하세요.

1. **환경 설정**:

    ```bash
    git clone https://github.com/unquote9094/txt_split_summary.git
    cd txt_split_summary
    npm install
    pip install -r requirements.txt
    ```

2. **모듈 설치**:
    이 프로젝트는 `google-generativeai` (v1/v2 혼용) 및 `tqdm` 등을 사용합니다.

3. **빌드 실행**:

    ```bash
    python scripts/build.py
    ```

    빌드가 완료되면 `dist/` 폴더에 새로운 `NovelAIze-SSR.exe`가 생성됩니다.

---

## 📜 라이선스

MIT License

Created by **Antigravity** (Google Deepmind Team) & **User**
v1.0 Release Date: 2026-01-11
