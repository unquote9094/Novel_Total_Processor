"""Stage 0 테스트 스크립트"""

from novel_total_processor.db.schema import get_database
from novel_total_processor.stages.stage0_indexing import FileScanner
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """Stage 0 테스트"""
    # DB 초기화
    db = get_database()
    db.initialize_schema()
    
    # 스캐너 실행
    scanner = FileScanner(db)
    
    # Test_Novels 폴더 스캔 (설정 파일 대신 직접 지정)
    test_folders = ["Test_Novels"]
    
    logger.info("Testing Stage 0 with Test_Novels folder...")
    files = scanner.scan_folders(test_folders)
    
    if files:
        duplicates = scanner.detect_duplicates(files)
        saved = scanner.save_to_db(files, duplicates)
        
        logger.info(f"\n📊 Results:")
        logger.info(f"  - Total files: {len(files)}")
        logger.info(f"  - Duplicates: {sum(len(fs) - 1 for fs in duplicates.values())}")
        logger.info(f"  - Saved to DB: {saved}")
    else:
        logger.warning("No files found in Test_Novels folder")
    
    db.close()


if __name__ == "__main__":
    main()
