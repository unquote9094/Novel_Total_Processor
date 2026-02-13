"""SQLite 데이터베이스 스키마 정의 및 초기화

설계서 v2 기준 7개 테이블:
1. files - 파일 인덱싱
2. novels - 소설 메타데이터
3. novel_extra - 부가 정보
4. episode_patterns - 화수 패턴
5. rename_plan - 파일명 변경 계획
6. processing_state - 파이프라인 상태
7. batch_logs - 배치 로그
"""

import sqlite3
from pathlib import Path
from typing import Optional
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)

# DB 스키마 정의
SCHEMA_SQL = """
-- ============================================
-- 파일 테이블 (물리적 파일 단위)
-- ============================================
CREATE TABLE IF NOT EXISTS files (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  novel_id        INTEGER,
  file_path       TEXT NOT NULL UNIQUE,
  file_name       TEXT NOT NULL,
  file_ext        TEXT NOT NULL,
  file_size       INTEGER,
  file_hash       TEXT NOT NULL,
  encoding        TEXT,
  is_duplicate    INTEGER DEFAULT 0,
  duplicate_of    INTEGER,
  indexed_at      TEXT DEFAULT (datetime('now','localtime')),
  FOREIGN KEY (duplicate_of) REFERENCES files(id)
);

CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash);

-- ============================================
-- 소설 테이블 (논리적 작품 단위)
-- ============================================
CREATE TABLE IF NOT EXISTS novels (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  title           TEXT NOT NULL,
  author          TEXT,
  genre           TEXT,
  tags            TEXT,
  status          TEXT,
  rating          REAL,
  cover_path      TEXT,
  cover_url       TEXT,
  episode_range   TEXT,
  episode_detail  TEXT,
  normalized_name TEXT,
  epub_path       TEXT,
  chapter_count   INTEGER,
  platform        TEXT,
  last_updated    TEXT,
  meta_cache_path TEXT,
  official_url    TEXT,
  reconciliation_log TEXT,
  created_at      TEXT DEFAULT (datetime('now','localtime')),
  updated_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================
-- 부가 도서 정보
-- ============================================
CREATE TABLE IF NOT EXISTS novel_extra (
  novel_id        INTEGER PRIMARY KEY,
  isbn            TEXT,
  publisher       TEXT,
  publish_date    TEXT,
  description     TEXT,
  source_url      TEXT,
  raw_json_path   TEXT,
  FOREIGN KEY (novel_id) REFERENCES novels(id)
);

-- ============================================
-- 화수 패턴 (AI 분석 결과)
-- ============================================
CREATE TABLE IF NOT EXISTS episode_patterns (
  file_id         INTEGER PRIMARY KEY,
  pattern_regex   TEXT,
  detected_start  INTEGER,
  detected_end    INTEGER,
  confidence      REAL,
  pattern_json    TEXT,
  FOREIGN KEY (file_id) REFERENCES files(id)
);

-- ============================================
-- 파일명 변경 계획 (검수용)
-- ============================================
CREATE TABLE IF NOT EXISTS rename_plan (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id         INTEGER NOT NULL,
  old_name        TEXT NOT NULL,
  new_name        TEXT NOT NULL,
  approved        INTEGER DEFAULT 0,
  applied         INTEGER DEFAULT 0,
  applied_at      TEXT,
  FOREIGN KEY (file_id) REFERENCES files(id)
);

-- ============================================
-- 파이프라인 처리 상태
-- ============================================
CREATE TABLE IF NOT EXISTS processing_state (
  file_id         INTEGER PRIMARY KEY,
  stage0_indexed  INTEGER DEFAULT 0,
  stage1_meta     INTEGER DEFAULT 0,
  stage2_episode  INTEGER DEFAULT 0,
  stage3_rename   INTEGER DEFAULT 0,
  stage4_split    INTEGER DEFAULT 0,
  stage5_epub     INTEGER DEFAULT 0,
  last_error      TEXT,
  last_stage      TEXT,
  reconciliation_log TEXT,
  updated_at      TEXT DEFAULT (datetime('now','localtime')),
  FOREIGN KEY (file_id) REFERENCES files(id)
);

-- ============================================
-- 배치 로그
-- ============================================
CREATE TABLE IF NOT EXISTS batch_logs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_name      TEXT,
  batch_type      TEXT,
  total_files     INTEGER,
  processed       INTEGER,
  success         INTEGER,
  failed          INTEGER,
  started_at      TEXT,
  finished_at     TEXT,
  duration_sec    INTEGER
);
"""


class Database:
    """SQLite 데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = "data/ntp.db"):
        """
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        logger.info(f"Database initialized: {self.db_path}")
    
    def connect(self) -> sqlite3.Connection:
        """데이터베이스 연결
        
        Returns:
            sqlite3.Connection 객체
        """
        if self.conn is None:
            self.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self.conn.row_factory = sqlite3.Row  # dict-like 접근
            logger.debug(f"Connected to database: {self.db_path}")
        return self.conn
    
    def initialize_schema(self) -> None:
        """스키마 초기화 (테이블 생성 및 마이그레이션)"""
        logger.info("Initializing database schema...")
        conn = self.connect()
        conn.executescript(SCHEMA_SQL)
        
        # 마이그레이션: 누락된 컬럼 자동 추가
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(novels)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # platform 컬럼 추가
            if "platform" not in columns:
                logger.info("Migrating: Adding 'platform' column to 'novels' table")
                cursor.execute("ALTER TABLE novels ADD COLUMN platform TEXT")
            
            # last_updated 컬럼 추가
            if "last_updated" not in columns:
                logger.info("Migrating: Adding 'last_updated' column to 'novels' table")
                cursor.execute("ALTER TABLE novels ADD COLUMN last_updated TEXT")
            
            # reconciliation_log 컬럼 추가 (novels)
            if "reconciliation_log" not in columns:
                logger.info("Migrating: Adding 'reconciliation_log' column to 'novels' table")
                cursor.execute("ALTER TABLE novels ADD COLUMN reconciliation_log TEXT")
            
            # processing_state 테이블 확인
            cursor.execute("PRAGMA table_info(processing_state)")
            ps_columns = [row[1] for row in cursor.fetchall()]
            if "reconciliation_log" not in ps_columns:
                logger.info("Migrating: Adding 'reconciliation_log' column to 'processing_state' table")
                cursor.execute("ALTER TABLE processing_state ADD COLUMN reconciliation_log TEXT")
            
            # [Hotfix] official_url 컬럼 추가 (novels)
            if "official_url" not in columns:
                logger.info("Migrating: Adding 'official_url' column to 'novels' table")
                cursor.execute("ALTER TABLE novels ADD COLUMN official_url TEXT")
                
            conn.commit()
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            
        logger.info("✅ Database schema initialized successfully")
    
    def close(self) -> None:
        """데이터베이스 연결 종료"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Database connection closed")
    
    def __enter__(self):
        """Context manager 진입"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.close()


def get_database(db_path: str = "data/ntp.db") -> Database:
    """데이터베이스 인스턴스 반환
    
    Args:
        db_path: 데이터베이스 파일 경로
    
    Returns:
        Database 인스턴스
    
    Example:
        >>> from novel_total_processor.db.schema import get_database
        >>> db = get_database()
        >>> db.initialize_schema()
    """
    return Database(db_path)
