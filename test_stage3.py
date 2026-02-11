"""Stage 3 테스트 스크립트

Stage 1 완료 후 실행 가능
"""

from novel_total_processor.db.schema import get_database
from novel_total_processor.stages.stage3_filename import FilenameGenerator
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """Stage 3 테스트"""
    # DB 연결
    db = get_database()
    
    # 파일명 생성기 실행
    generator = FilenameGenerator(db)
    
    # 테스트: 처음 10개 파일만 처리
    logger.info("Testing Stage 3 with first 10 files...")
    results = generator.run(limit=10)
    
    logger.info(f"\n📊 Results:")
    logger.info(f"  - Total: {results['total']}")
    logger.info(f"  - Mapping file: {results['mapping_file']}")
    
    if results['mapping_file']:
        logger.info(f"\n✅ Please review the mapping file:")
        logger.info(f"   {results['mapping_file']}")
    
    db.close()


if __name__ == "__main__":
    main()
