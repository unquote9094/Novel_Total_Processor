"""전역 로깅 설정 모듈

모든 모듈에서 `from novel_total_processor.utils.logger import get_logger` 로 사용.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# 로그 디렉토리
LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 로그 포맷
FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
CONSOLE_FORMAT = "%(levelname)-8s | %(name)s | %(message)s"

# 날짜별 로그 파일
LOG_FILE = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"


def setup_logging(level: str = "DEBUG", console_level: str = "INFO") -> None:
    """전역 로깅 설정
    
    Args:
        level: 파일 로그 레벨 (DEBUG/INFO/WARNING/ERROR)
        console_level: 콘솔 로그 레벨 (기본 INFO)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 최소 레벨은 DEBUG
    
    # 기존 핸들러 제거
    root_logger.handlers.clear()
    
    # 파일 핸들러 (DEBUG 레벨까지 전부 기록)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(getattr(logging, level.upper()))
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    root_logger.addHandler(file_handler)
    
    # 콘솔 핸들러 (INFO 이상만 표시)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper()))
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    root_logger.addHandler(console_handler)
    
    # 초기 로그
    root_logger.info(f"Logging initialized: file={LOG_FILE}, level={level}")


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """로거 인스턴스 반환
    
    Args:
        name: 로거 이름 (보통 __name__ 사용)
    
    Returns:
        logging.Logger 인스턴스
    
    Example:
        >>> from novel_total_processor.utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.debug("디버그 메시지")
        >>> logger.info("정보 메시지")
    """
    return logging.getLogger(name or __name__)


# 모듈 임포트 시 자동 초기화
setup_logging()
