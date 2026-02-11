"""로거 테스트 스크립트"""

from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)

logger.debug("디버그 메시지 (파일에만 기록)")
logger.info("정보 메시지 (콘솔 + 파일)")
logger.warning("경고 메시지")
logger.error("에러 메시지")

print("\n✅ 로거 테스트 완료!")
print(f"📁 로그 파일 확인: data/logs/")
