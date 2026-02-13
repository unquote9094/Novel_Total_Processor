import sqlite3

db_path = "data/ntp.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. 문제의 파일 찾기
cursor.execute("SELECT id, file_hash, file_name FROM files WHERE file_name LIKE '%남녀역전%'")
rows = cursor.fetchall()

for row in rows:
    fid, fhash, fname = row
    print(f"Resetting file: {fname} (ID: {fid}, Hash: {fhash})")
    
    # 상태 초기화 (Stage 3부터 다시 시작)
    cursor.execute("""
        UPDATE processing_state 
        SET stage3_rename = 0, stage4_split = 1, stage5_epub = 0, last_stage = 'stage4'
        WHERE file_id = ?
    """, (fid,))
    
    # 소설 정보의 EPUB 경로도 삭제
    cursor.execute("UPDATE novels SET epub_path = NULL WHERE id = (SELECT novel_id FROM files WHERE id = ?)", (fid,))

conn.commit()
conn.close()
print("Done.")
