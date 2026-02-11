"""Stage 2 테스트 스크립트

환경변수 GEMINI_API_KEY 필요
Stage 1 완료 후 실행 가능
"""

import os
from novel_total_processor.db.schema import get_database
from novel_total_processor.stages.stage2_episode import EpisodePatternDetector
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """Stage 2 테스트"""
    # API 키 확인
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY environment variable not set!")
        return
    
    # DB 연결
    db = get_database()
    
    # 패턴 감지기 실행
    detector = EpisodePatternDetector(db)
    
    # 테스트: 처음 5개 파일만 처리
    logger.info("Testing Stage 2 with first 5 files...")
    results = detector.run(limit=5)
    
    logger.info(f"\n📊 Results:")
    logger.info(f"  - Total: {results['total']}")
    logger.info(f"  - Success: {results['success']}")
    logger.info(f"  - Failed: {results['failed']}")
    
    db.close()


if __name__ == "__main__":
    main()
