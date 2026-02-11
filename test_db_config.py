"""DB 스키마 및 Config 로더 테스트"""

from novel_total_processor.db.schema import get_database
from novel_total_processor.config.loader import get_config, get_rules
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)

def test_database():
    """데이터베이스 스키마 테스트"""
    logger.info("=" * 50)
    logger.info("Testing Database Schema")
    logger.info("=" * 50)
    
    db = get_database()
    db.initialize_schema()
    
    # 테이블 목록 확인
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    logger.info(f"✅ Created {len(tables)} tables:")
    for table in tables:
        logger.info(f"   - {table}")
    
    db.close()
    logger.info("✅ Database test passed!")


def test_config():
    """설정 로더 테스트"""
    logger.info("=" * 50)
    logger.info("Testing Config Loader")
    logger.info("=" * 50)
    
    config = get_config()
    logger.info(f"✅ Source folders: {len(config.paths.source_folders)}")
    logger.info(f"   - {config.paths.source_folders}")
    logger.info(f"✅ Database: {config.paths.database}")
    logger.info(f"✅ Gemini model: {config.api.gemini.model}")
    logger.info(f"✅ Perplexity search: {config.api.perplexity.search_model}")
    logger.info(f"✅ Max workers: {config.processing.max_workers}")
    logger.info(f"✅ EPUB version: {config.epub.version}")
    logger.info("✅ Config test passed!")


def test_rules():
    """규칙 로더 테스트"""
    logger.info("=" * 50)
    logger.info("Testing Rules Loader")
    logger.info("=" * 50)
    
    rules = get_rules()
    logger.info(f"✅ Title max length: {rules.title['max_length']}")
    logger.info(f"✅ Completed marker: {rules.episode['completed_marker']}")
    logger.info(f"✅ Genre mappings: {len(rules.genre['mapping'])}")
    logger.info(f"✅ Filename separator: {rules.filename['separator']}")
    logger.info(f"✅ Max total length: {rules.filename['max_total_length']}")
    logger.info("✅ Rules test passed!")


if __name__ == "__main__":
    test_database()
    print()
    test_config()
    print()
    test_rules()
    print()
    logger.info("=" * 50)
    logger.info("🎉 All tests passed!")
    logger.info("=" * 50)
