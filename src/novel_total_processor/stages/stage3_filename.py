"""Stage 3: 파일명 생성

rules.yml 기반 파일명 규칙 엔진, 검수용 매핑 파일 생성
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from novel_total_processor.utils.logger import get_logger
from novel_total_processor.db.schema import Database
from novel_total_processor.config.loader import get_config, get_rules

logger = get_logger(__name__)


class FilenameGenerator:
    """파일명 생성기 (Stage 3)"""
    
    def __init__(self, db: Database):
        """
        Args:
            db: Database 인스턴스
        """
        self.db = db
        self.config = get_config()
        self.rules = get_rules()
        logger.info("FilenameGenerator initialized")
    
    def get_pending_files(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Stage 3 대기 중인 파일 조회
        
        Args:
            limit: 최대 파일 수
        
        Returns:
            파일 정보 리스트
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        query = """
            SELECT f.id, f.file_path, f.file_name, f.file_ext, n.title, n.author, n.genre, 
                   n.tags, n.status, n.episode_range, n.rating, n.chapter_count
            FROM files f
            JOIN processing_state ps ON f.id = ps.file_id
            JOIN novels n ON f.novel_id = n.id
            WHERE ps.stage1_meta = 1 AND ps.stage3_rename = 0
            AND f.is_duplicate = 0 AND f.file_ext IN ('.txt', '.epub')
            ORDER BY f.id ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        files = []
        for row in rows:
            files.append({
                "id": row[0],
                "file_path": row[1],
                "filename": row[2],
                "ext": row[3],
                "title": row[4],
                "author": row[5],
                "genre": row[6],
                "tags": self._parse_tags(row[7]) if row[7] else [],
                "status": row[8],
                "episode_range": row[9],
                "rating": row[10],
                "chapter_count": row[11]
            })
        
        logger.info(f"Found {len(files)} files pending for Stage 3")
        return files
    
    def generate_filename(self, metadata: Dict[str, Any]) -> str:
        """파일명 생성
        
        Args:
            metadata: 메타데이터 딕셔너리
        
        Returns:
            새 파일명 (확장자 포함)
        
        Format: 제목__화수_상태__★별점__장르__작가__태그.ext
        """
        parts = []
        
        # 1. 제목 정규화
        title = self._normalize_title(metadata["title"])
        parts.append(title)
        
        # 2. 화수_상태 (파일명 힌트 최우선 적용: M-46)
        original_range = metadata.get("episode_range")
        original_status = metadata.get("status")
        chapter_count = metadata.get("chapter_count")
        
        # 파일명에서 힌트 추출 (예: 1~321화)
        hint_range = None
        hint_nums = re.findall(r'\((\d+~\d+)\)', metadata["filename"])
        if not hint_nums:
            hint_nums = re.findall(r'\((\d+)\)', metadata["filename"])
            if hint_nums: hint_range = f"1~{hint_nums[0]}화"
        else:
            hint_range = f"{hint_nums[0]}화"
            
        reconciled_range = original_range
        reconciled_status = original_status
        
        # 파일명 힌트가 있다면 무조건 최우선 (이미 검증된 정보로 간주)
        if hint_range:
            reconciled_range = hint_range
        elif chapter_count and chapter_count > 0:
            reconciled_range = f"1~{chapter_count}화"
        
        # [Smart Extension] 실물 화수와 웹 화수가 다를 경우 확장 태깅 (M-49)
        # 웹 화수(original_range)에서 숫자 추출
        web_total = 0
        if original_range:
            web_nums = re.findall(r'(\d+)', original_range)
            if web_nums: web_total = int(web_nums[-1])
            
        real_total = chapter_count if chapter_count else 0
        if not real_total and hint_range:
            hint_nums_extracted = re.findall(r'(\d+)', hint_range)
            if hint_nums_extracted: real_total = int(hint_nums_extracted[-1])

        # 화수 불일치 시 상태값 확장
        if web_total > 0 and real_total > 0 and web_total != real_total:
            diff_tag = f"({real_total}_{web_total}화)"
            if reconciled_status:
                reconciled_status = f"{reconciled_status}_부분{diff_tag}"
            else:
                reconciled_status = f"부분{diff_tag}"
        
        episode_status = self._format_episode_status(
            reconciled_range,
            reconciled_status
        )
        parts.append(episode_status)
        
        # 3. ★별점
        rating = self._format_rating(metadata.get("rating"))
        if "Unknown" not in rating and "미평가" not in rating:
            parts.append(rating)
        
        # 4. 장르
        genre = self._normalize_genre(metadata.get("genre"))
        if genre and "Unknown" not in genre:
            parts.append(genre)
        
        # 5. 작가
        author = self._normalize_author(metadata.get("author"))
        if author and "Unknown" not in author:
            parts.append(author)
        
        # 6. 태그
        tags = self._format_tags(metadata.get("tags", []))
        if tags:
            parts.append(tags)
        
        # 구분자로 결합 (빈 필드는 걸러내기)
        separator = self.rules.filename["separator"]
        parts = [p for p in parts if p and p.strip() and "Unknown" not in p]
        filename = separator.join(parts)
        
        # 금지 문자 제거
        filename = self._sanitize_filename(filename)
        
        # 길이 제한
        filename = self._truncate_filename(filename, metadata["ext"])
        
        # 확장자 추가
        return f"{filename}{metadata['ext']}"
    
    def _normalize_title(self, title: str) -> str:
        """제목 정규화
        
        Args:
            title: 원본 제목
        
        Returns:
            정규화된 제목
        """
        # 접두사 제거
        for pattern in self.rules.title["remove_prefixes"]:
            title = re.sub(pattern, "", title)
        
        # 접미사 제거
        for pattern in self.rules.title["remove_suffixes"]:
            title = re.sub(pattern, "", title)
        
        # 공백 정리
        title = " ".join(title.split())
        
        # 최대 길이
        max_len = self.rules.title["max_length"]
        if len(title.encode("utf-8")) > max_len:
            # 바이트 단위로 자르기
            title_bytes = title.encode("utf-8")[:max_len]
            title = title_bytes.decode("utf-8", errors="ignore")
        
        return title.strip()
    
    def _format_episode_status(self, episode_range: Optional[str], status: Optional[str]) -> str:
        """화수_상태 포맷
        
        Args:
            episode_range: 화수 범위 (예: "1~340화")
            status: 상태 (완결/연재/휴재)
        
        Returns:
            "1~340화_완결" 형식
        """
        parts = []
        
        if episode_range:
            parts.append(episode_range)
        else:
            parts.append(self.rules.episode["oneshot_marker"])
        
        if status:
            # 영어 상태값 한글 매핑 (M-32)
            status_map = {
                "completed": "완결",
                "Completed": "완결",
                "ongoing": "연재",
                "Ongoing": "연재",
                "연재중": "연재",
                "연재": "연재",
                "hiatus": "휴재",
                "Hiatus": "휴재"
            }
            mapped_status = status_map.get(status, status)
            
            # 룰 기반 최종 변환
            status_text = self.rules.status.get(mapped_status.lower(), mapped_status)
            parts.append(status_text)
        
        return "_".join(parts) if parts else "미확인"
    
    def _format_rating(self, rating: Optional[float]) -> str:
        """별점 포맷
        
        Args:
            rating: 별점 (0.0~5.0)
        
        Returns:
            "★4.5" 형식
        """
        if rating is None:
            return self.rules.rating["unknown"]
        
        symbol = self.rules.rating["symbol"]
        decimal_places = self.rules.rating["decimal_places"]
        
        return f"{symbol}{rating:.{decimal_places}f}"
    
    def _normalize_genre(self, genre: Optional[str]) -> str:
        """장르 정규화
        
        Args:
            genre: 원본 장르
        
        Returns:
            표준 장르명
        """
        if not genre:
            return self.rules.genre["default"]
        
        # 매핑 테이블에서 찾기
        mapping = self.rules.genre["mapping"]
        return mapping.get(genre, genre)
    
    def _normalize_author(self, author: Optional[str]) -> str:
        """작가명 정규화
        
        Args:
            author: 원본 작가명
        
        Returns:
            정규화된 작가명
        """
        if not author:
            return "작가미상"
        
        # 패턴 제거
        for pattern in self.rules.author["remove_patterns"]:
            author = re.sub(pattern, "", author)
        
        # 최대 길이
        max_len = self.rules.author["max_length"]
        if len(author.encode("utf-8")) > max_len:
            author_bytes = author.encode("utf-8")[:max_len]
            author = author_bytes.decode("utf-8", errors="ignore")
        
        return author.strip()
    
    def _format_tags(self, tags: List[str]) -> str:
        """태그 포맷
        
        Args:
            tags: 태그 리스트
        
        Returns:
            "태그1,태그2,태그3" 형식
        """
        if not tags:
            return ""
        
        # 우선순위 태그 먼저
        priority = self.rules.tags["priority"]
        priority_tags = [t for t in tags if t in priority]
        other_tags = [t for t in tags if t not in priority]
        
        # 합치기
        sorted_tags = priority_tags + other_tags
        
        # 최대 개수
        max_count = self.rules.tags["max_in_filename"]
        selected_tags = sorted_tags[:max_count]
        
        # 구분자로 결합
        separator = self.rules.tags["separator"]
        return separator.join(selected_tags)
    
    def _sanitize_filename(self, filename: str) -> str:
        """금지 문자 제거
        
        Args:
            filename: 원본 파일명
        
        Returns:
            정리된 파일명
        """
        forbidden = self.rules.filename["forbidden_chars"]
        replacement = self.rules.filename["replacement_char"]
        
        for char in forbidden:
            filename = filename.replace(char, replacement)
        
        return filename
    
    def _truncate_filename(self, filename: str, ext: str) -> str:
        """파일명 길이 제한
        
        Args:
            filename: 파일명 (확장자 제외)
            ext: 확장자
        
        Returns:
            잘린 파일명
        """
        max_len = self.rules.filename["max_total_length"]
        ext_len = len(ext.encode("utf-8"))
        available = max_len - ext_len
        
        filename_bytes = filename.encode("utf-8")
        if len(filename_bytes) > available:
            filename_bytes = filename_bytes[:available]
            filename = filename_bytes.decode("utf-8", errors="ignore")
        
        return filename
    
    def _apply_renames(self, file_id: int, old_name: str, new_name: str) -> bool:
        """실제 파일명 변경 실행
        
        Args:
            file_id: 파일 ID
            old_name: 기존 파일명
            new_name: 새 파일명
            
        Returns:
            성공 여부
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # 파일 경로 조회
        cursor.execute("SELECT file_path FROM files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        if not row:
            logger.error(f"File not found in DB: ID {file_id}")
            return False
            
        old_path = Path(row[0])
        if not old_path.exists():
            logger.error(f"File not found on disk: {old_path}")
            return False
            
        # 새 경로 생성
        new_path = old_path.with_name(new_name)
        
        try:
            # 실제 이름 변경
            old_path.rename(new_path)
            
            # DB의 file_path, file_name 업데이트
            cursor.execute("""
                UPDATE files 
                SET file_path = ?, file_name = ?
                WHERE id = ?
            """, (str(new_path), new_path.stem, file_id))
            
            conn.commit()
            logger.info(f"   [Rename Executed] {old_path.name} -> {new_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to rename file: {e}")
            return False
    
    def save_rename_plan(self, file_id: int, old_name: str, new_name: str) -> None:
        """파일명 변경 계획 저장
        
        Args:
            file_id: 파일 ID
            old_name: 기존 파일명
            new_name: 새 파일명
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO rename_plan (file_id, old_name, new_name)
            VALUES (?, ?, ?)
        """, (file_id, old_name, new_name))
        
        # processing_state 업데이트
        cursor.execute("""
            UPDATE processing_state
            SET stage3_rename = 1, last_stage = 'stage3'
            WHERE file_id = ?
        """, (file_id,))
        
        conn.commit()
    
    def generate_mapping_file(self, plans: List[Tuple[str, str]]) -> str:
        """검수용 매핑 파일 생성
        
        Args:
            plans: [(old_name, new_name), ...]
        
        Returns:
            생성된 파일 경로
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"data/mapping_result_{timestamp}.txt")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("=" * 100 + "\n")
            f.write(f"파일명 변경 계획 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 100 + "\n\n")
            
            for old_name, new_name in plans:
                f.write(f"{old_name}\n")
                f.write(f"  → {new_name}\n\n")
        
        logger.info(f"✅ Mapping file created: {output_path}")
        return str(output_path)
    
    def run(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Stage 3 실행"""
        logger.info("=" * 50)
        logger.info("Stage 3: Filename Generation")
        logger.info("=" * 50)
        
        # 대기 파일 조회
        files = self.get_pending_files(limit)
        
        if not files:
            logger.warning("No files to process")
            return {"total": 0, "renamed": 0, "mapping_file": None}
        
        result = self.process_files(files)
        
        logger.info("=" * 50)
        logger.info(f"✅ Stage 3 Complete: {result['renamed']} files renamed")
        if result['mapping_file']:
            logger.info(f"📄 Mapping file: {result['mapping_file']}")
        logger.info("=" * 50)
        
        return result

    def process_single_file(self, file_id: int) -> bool:
        """단일 파일에 대해 명명 규칙 재적용 및 이름 변경 (M-49)"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        query = """
            SELECT f.id, f.file_path, f.file_name, f.file_ext, n.title, n.author, n.genre, 
                   n.tags, n.status, n.episode_range, n.rating, n.chapter_count, n.reconciliation_log
            FROM files f
            JOIN novels n ON f.novel_id = n.id
            WHERE f.id = ?
        """
        cursor.execute(query, (file_id,))
        row = cursor.fetchone()
        if not row:
            return False
            
        file_info = {
            "id": row[0],
            "file_path": row[1],
            "filename": row[2],
            "ext": row[3],
            "title": row[4],
            "author": row[5],
            "genre": row[6],
            "tags": self._parse_tags(row[7]) if row[7] else [],
            "status": row[8],
            "episode_range": row[9],
            "rating": row[10],
            "chapter_count": row[11],
            "reconciliation_log": row[12],
            "file_name": row[2] # generate_filename에서 metadata.get("filename") 사용하므로 맞춰줌
        }
        # generate_filename 내부에서 metadata["filename"]을 사용하므로 키를 맞춰줌
        file_info["filename"] = row[2]
        
        new_name = self.generate_filename(file_info)
        return self._apply_renames(file_info["id"], file_info["filename"], new_name)

    def process_files(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """파일 리스트 처리"""
        plans = []
        success_count = 0
        for i, file in enumerate(files):
            new_name = self.generate_filename(file)
            
            if self._apply_renames(file["id"], file["filename"], new_name):
                self.save_rename_plan(file["id"], file["filename"], new_name)
                plans.append((file["filename"], new_name))
                success_count += 1
            else:
                logger.error(f"  ❌ Failed to rename {file['filename']}")
        
        mapping_file = self.generate_mapping_file(plans) if plans else None
        return {
            "total": len(files),
            "renamed": success_count,
            "mapping_file": mapping_file
        }

    def _parse_tags(self, tags_raw: str) -> List[str]:
        """태그 문자열 파싱 (JSON 리스트 또는 쉼표 구분 문자열)"""
        if not tags_raw:
            return []
            
        tags_raw = tags_raw.strip()
        if tags_raw.startswith("["):
            try:
                import json
                tags_list = json.loads(tags_raw)
                if isinstance(tags_list, list):
                    return [str(t).strip() for t in tags_list if t]
            except:
                pass
        
        # 쉼표 구분 문자열로 처리
        return [t.strip() for t in tags_raw.split(",") if t.strip()]
