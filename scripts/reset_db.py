import sqlite3
import os
from pathlib import Path

def reset_db():
    db_path = "data/ntp.db"
    
    if os.path.exists(db_path):
        print(f"Removing database: {db_path}")
        try:
            # 파일을 닫아야 삭제될 수 있음 (보통 이 스크립트는 독립 실행)
            os.remove(db_path)
            print("Successfully deleted the database file.")
        except Exception as e:
            print(f"Failed to delete database file: {e}")
            print("Try connecting and dropping tables instead...")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS processing_state")
            cursor.execute("DROP TABLE IF EXISTS files")
            cursor.execute("DROP TABLE IF EXISTS novels")
            cursor.execute("DROP TABLE IF EXISTS rename_plan")
            cursor.execute("DROP TABLE IF EXISTS episode_patterns")
            cursor.execute("DROP TABLE IF EXISTS novel_extra")
            cursor.execute("DROP TABLE IF EXISTS batch_logs")
            conn.commit()
            conn.close()
            print("Dropped all tables.")
    else:
        print("Database file not found. Nothing to reset.")

if __name__ == "__main__":
    reset_db()
