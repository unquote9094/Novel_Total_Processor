# Novel Total Processor

소설 파일 자동 처리 파이프라인 (메타데이터 추출, EPUB 변환, 파일명 정규화)

## 🚀 빠른 시작

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
export GEMINI_API_KEY="your_gemini_api_key"
export PERPLEXITY_API_KEY="your_perplexity_api_key"

# 실행
python -m novel_total_processor.cli
```

## 📦 기능

- ✅ TXT/EPUB 파일 자동 인덱싱
- ✅ AI 기반 메타데이터 추출 (Gemini + Perplexity)
- ✅ 파일명 자동 정규화 (`제목__화수_상태__★별점__장르__작가__태그.ext`)
- ✅ EPUB 생성 및 메타데이터 업데이트
- ✅ Rich UI 대시보드
- ✅ 일일 배치 처리

## 📁 프로젝트 구조

```
Novel_Total_Processor/
├── src/novel_total_processor/  # 소스 코드
├── config/                      # 설정 파일
├── data/                        # 데이터 (DB, 로그, 표지)
├── docs/                        # 문서
└── pyproject.toml               # 프로젝트 설정
```

## 📖 문서

- [설계서 v2](docs/Novel_Total_Processor_설계서_v2.md)
- [구현 계획](docs/implementation_plan_v1.md)
- [Perplexity API 가이드](docs/Perplexity-API.md)

## 📝 라이선스

MIT
