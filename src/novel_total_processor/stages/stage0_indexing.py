"""Stage 0: 파일 인덱싱

다중 폴더 재귀 스캔, XXHash 계산, 중복 감지, DB 등록
"""

import os
import xxhash
import chardet
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.db.schema import Database
from novel_total_processor.config.loader import get_config

logger = get_logger(__name__)

# 허용 확장자
ALLOWED_EXTENSIONS = {".txt", ".epub"}

# 제외할 확장자 (실행 파일, 시스템 파일 등)
EXCLUDED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".ps1",
    ".dll", ".so", ".dylib",
    ".json", ".xml", ".yml", ".yaml",
    ".zip", ".rar", ".7z", ".tar", ".gz"
}

# 최소 파일 크기 (512바이트 미만 제외)
MIN_FILE_SIZE = 512


@dataclass
class FileInfo:
    """파일 정보"""
    path: str
    name: str
    ext: str
    size: int
    hash: str
    encoding: Optional[str] = None


class FileScanner:
    """파일 스캐너 (Stage 0)"""
    
    def __init__(self, db: Database):
        """
        Args:
            db: Database 인스턴스
        """
        self.db = db
        self.config = get_config()
        logger.info("FileScanner initialized")
    
    def scan_folders(self, folders: Optional[List[str]] = None) -> List[FileInfo]:
        """폴더 재귀 스캔
        
        Args:
            folders: 스캔할 폴더 목록 (None이면 config에서 읽음)
        
        Returns:
            FileInfo 리스트
        """
        if folders is None:
            folders = self.config.paths.source_folders or []
        
        # None이나 빈 문자열 필터링
        folders = [f for f in folders if f]
        
        logger.info(f"Scanning {len(folders)} folders...")
        
        # 실종된 파일 정리 (M-30: Prune Missing Files)
        self.prune_missing_files()
        
        all_files: List[FileInfo] = []
        
        for folder in folders:
            folder_path = Path(folder)
            if not folder_path.exists():
                logger.warning(f"Folder not found: {folder}")
                continue
            
            logger.info(f"Scanning: {folder}")
            files = self._scan_folder(folder_path)
            all_files.extend(files)
            logger.info(f"  Found {len(files)} files")
        
        logger.info(f"✅ Total files found: {len(all_files)}")
        return all_files
    
    def _scan_folder(self, folder: Path) -> List[FileInfo]:
        """단일 폴더 재귀 스캔
        
        Args:
            folder: 폴더 경로
        
        Returns:
            FileInfo 리스트
        """
        files: List[FileInfo] = []
        
        filenames_all = []
        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                filenames_all.append(Path(root) / filename)
        
        # 이름순 정렬 (ID 순서 고정)
        for file_path in sorted(filenames_all):
                
                # 확장자 필터
                ext = file_path.suffix.lower()
                if ext not in ALLOWED_EXTENSIONS:
                    continue
                
                # 크기 필터
                try:
                    size = file_path.stat().st_size
                    if size < MIN_FILE_SIZE:
                        logger.debug(f"Skipped (too small): {file_path}")
                        continue
                except Exception as e:
                    logger.warning(f"Failed to get size: {file_path} - {e}")
                    continue
                
                # 인코딩 감지 및 자동 UTF-8 변환 (TXT만)
                encoding = None
                if ext == ".txt":
                    encoding = self._detect_encoding(file_path)
                    if encoding:
                        # UTF-8이 아니면 변환 실행
                        self._ensure_utf8(file_path, encoding)
                        encoding = "utf-8"  # 변환 후엔 utf-8임
                
                # 파일 정보 다시 읽기 (변환 후 크기/해시가 달라질 수 있음)
                try:
                    size = file_path.stat().st_size
                    file_hash = self._calculate_hash(file_path)
                except Exception as e:
                    logger.error(f"Failed to process after conversion: {file_path} - {e}")
                    continue

                files.append(FileInfo(
                    path=str(file_path.absolute()),
                    name=file_path.name,
                    ext=ext,
                    size=size,
                    hash=file_hash,
                    encoding=encoding
                ))
        
        return files

    def _ensure_utf8(self, file_path: Path, encoding: str) -> bool:
        """파일을 UTF-8로 변환 및 저장
        
        Args:
            file_path: 파일 경로
            encoding: 현재 감지된 인코딩
            
        Returns:
            성공 여부
        """
        if encoding.lower() in ['utf-8', 'utf-8-sig', 'ascii']:
            return True
            
        try:
            logger.info(f"   🔄 Converting to UTF-8: {file_path.name} ({encoding} -> utf-8)")
            
            # 1. 감지된 인코딩으로 읽기
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()
            
            # 2. UTF-8로 덮어쓰기
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            return True
        except Exception as e:
            logger.error(f"   ❌ Conversion failed: {file_path} - {e}")
            return False
    
    def _calculate_hash(self, file_path: Path) -> str:
        """XXHash 계산
        
        Args:
            file_path: 파일 경로
        
        Returns:
            16진수 해시 문자열
        """
        hasher = xxhash.xxh64()
        
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    def _detect_encoding(self, file_path: Path, sample_size: int = 10000) -> Optional[str]:
        """인코딩 감지
        
        Args:
            file_path: 파일 경로
            sample_size: 샘플 크기 (바이트)
        
        Returns:
            인코딩 이름 (예: 'utf-8', 'cp949')
        """
        try:
            with open(file_path, "rb") as f:
                sample = f.read(sample_size)
            
            result = chardet.detect(sample)
            encoding = result.get("encoding")
            confidence = result.get("confidence", 0)
            
            if confidence > 0.7:
                logger.debug(f"Encoding detected: {encoding} ({confidence:.2f}) - {file_path.name}")
                return encoding
            else:
                logger.debug(f"Low confidence encoding: {encoding} ({confidence:.2f}) - {file_path.name}")
                return None
        except Exception as e:
            logger.warning(f"Encoding detection failed: {file_path} - {e}")
            return None
    
    def detect_duplicates(self, files: List[FileInfo]) -> Dict[str, List[FileInfo]]:
        """중복 파일 감지
        
        Args:
            files: FileInfo 리스트
        
        Returns:
            해시별 중복 파일 그룹 {hash: [FileInfo, ...]}
        """
        hash_map: Dict[str, List[FileInfo]] = {}
        
        for file in files:
            if file.hash not in hash_map:
                hash_map[file.hash] = []
            hash_map[file.hash].append(file)
        
        # 중복만 필터링 (2개 이상)
        duplicates = {h: fs for h, fs in hash_map.items() if len(fs) > 1}
        
        if duplicates:
            logger.warning(f"⚠️ Found {len(duplicates)} duplicate groups ({sum(len(fs) for fs in duplicates.values())} files)")
            for hash_val, dup_files in duplicates.items():
                logger.debug(f"  Hash {hash_val[:8]}... : {len(dup_files)} files")
                for f in dup_files:
                    logger.debug(f"    - {f.name}")
        else:
            logger.info("✅ No duplicates found")
        
        return duplicates
    
    def save_to_db(self, files: List[FileInfo], duplicates: Dict[str, List[FileInfo]]) -> int:
        """DB에 저장
        
        Args:
            files: FileInfo 리스트
            duplicates: 중복 파일 그룹
        
        Returns:
            저장된 파일 수
        """
        logger.info("Saving to database...")
        conn = self.db.connect()
        cursor = conn.cursor()
        
        saved_count = 0
        
        for file in files:
            # 중복 체크
            is_duplicate = 0
            duplicate_of = None
            
            if file.hash in duplicates:
                dup_group = duplicates[file.hash]
                # 첫 번째 파일을 원본으로
                if file.path != dup_group[0].path:
                    is_duplicate = 1
                    # 원본 파일 ID 찾기
                    cursor.execute(
                        "SELECT id FROM files WHERE file_path = ?",
                        (dup_group[0].path,)
                    )
                    result = cursor.fetchone()
                    if result:
                        duplicate_of = result[0]
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO files 
                    (file_path, file_name, file_ext, file_size, file_hash, encoding, is_duplicate, duplicate_of)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file.path,
                    file.name,
                    file.ext,
                    file.size,
                    file.hash,
                    file.encoding,
                    is_duplicate,
                    duplicate_of
                ))
                
                # processing_state 초기화
                file_id = cursor.lastrowid
                cursor.execute("""
                    INSERT OR REPLACE INTO processing_state (file_id, stage0_indexed)
                    VALUES (?, 1)
                """, (file_id,))
                
                saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save: {file.path} - {e}")
        
        conn.commit()
        logger.info(f"✅ Saved {saved_count} files to database")
        return saved_count
    
    def run(self) -> Tuple[int, int]:
        """Stage 0 실행
        
        Returns:
            (총 파일 수, 중복 파일 수)
        """
        logger.info("=" * 50)
        logger.info("Stage 0: File Indexing")
        logger.info("=" * 50)
        
        # 1. 스캔
        files = self.scan_folders()
        
        if not files:
            logger.warning("No files found!")
            return 0, 0
        
        # 2. 중복 감지
        duplicates = self.detect_duplicates(files)
        duplicate_count = sum(len(fs) - 1 for fs in duplicates.values())
        
        # 3. DB 저장
        saved = self.save_to_db(files, duplicates)
        
        logger.info("=" * 50)
        logger.info(f"✅ Stage 0 Complete: {saved} files indexed, {duplicate_count} duplicates")
        logger.info("=" * 50)
        
        return saved, duplicate_count
    def prune_missing_files(self) -> None:
        """DB에는 있으나 디스크에 실재하지 않는 파일 레코드 정리 (M-30)"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, file_path FROM files")
        rows = cursor.fetchall()
        
        missing_ids = []
        for fid, fpath in rows:
            if not Path(fpath).exists():
                missing_ids.append(fid)
        
        if missing_ids:
            logger.info(f"🗑️  실종된 파일 {len(missing_ids)}개를 DB에서 정리 중...")
            # 파이프라인 상태 및 패턴 데이터도 함께 삭제 (CASCADE 제약 조건이 없을 경우 대비)
            placeholders = ",".join(["?"] * len(missing_ids))
            
            cursor.execute(f"DELETE FROM processing_state WHERE file_id IN ({placeholders})", missing_ids)
            cursor.execute(f"DELETE FROM episode_patterns WHERE file_id IN ({placeholders})", missing_ids)
            cursor.execute(f"DELETE FROM rename_plan WHERE file_id IN ({placeholders})", missing_ids)
            cursor.execute(f"DELETE FROM files WHERE id IN ({placeholders})", missing_ids)
            
            conn.commit()
            logger.info(f"✅ 정리 완료")
