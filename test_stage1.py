"""Stage 1 테스트 스크립트

환경변수 GEMINI_API_KEY 필요
PERPLEXITY_API_KEY는 선택 (없으면 Perplexity 기능 비활성화)
"""

import os
from novel_total_processor.db.schema import get_database
from novel_total_processor.stages.stage1_metadata import MetadataCollector
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """Stage 1 테스트"""
    # API 키 확인
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY environment variable not set!")
        logger.info("Please set: export GEMINI_API_KEY='your_api_key'")
        return
    
    # DB 연결
    db = get_database()
    
    # 수집기 실행
    collector = MetadataCollector(db)
    
    # 테스트: 처음 10개 파일만 처리
    logger.info("Testing Stage 1 with first 10 files...")
    results = collector.run(limit=10)
    
    logger.info(f"\n📊 Results:")
    logger.info(f"  - Total: {results['total']}")
    logger.info(f"  - Success: {results['success']}")
    logger.info(f"  - Failed: {results['failed']}")
    
    db.close()


if __name__ == "__main__":
    main()
