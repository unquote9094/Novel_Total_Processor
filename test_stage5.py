"""Stage 5 테스트 스크립트

Stage 3 완료 후 실행 가능
"""

from novel_total_processor.db.schema import get_database
from novel_total_processor.stages.stage5_epub import EPUBGenerator
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """Stage 5 테스트"""
    # DB 연결
    db = get_database()
    
    # EPUB 생성기 실행
    generator = EPUBGenerator(db)
    
    # 테스트: 처음 3개 파일만 처리
    logger.info("Testing Stage 5 with first 3 files...")
    results = generator.run(limit=3)
    
    logger.info(f"\n📊 Results:")
    logger.info(f"  - Total: {results['total']}")
    logger.info(f"  - Success: {results['success']}")
    logger.info(f"  - Failed: {results['failed']}")
    
    if results['success'] > 0:
        logger.info(f"\n✅ EPUB files created in: {generator.output_dir}")
    
    db.close()


if __name__ == "__main__":
    main()
