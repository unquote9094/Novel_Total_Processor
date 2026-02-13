import sqlite3
import os

def diag():
    db_path = "e:/DEVz/10_Novel_Total_Processor/data/ntp.db"
    if not os.path.exists(db_path):
        print("DB not found")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- Table Info: files ---")
    cursor.execute("PRAGMA table_info(files)")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Triggers ---")
    cursor.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type = 'trigger'")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Processing State Sample ---")
    cursor.execute("SELECT * FROM processing_state LIMIT 5")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Files Sample ---")
    cursor.execute("SELECT id, file_name, is_duplicate FROM files LIMIT 5")
    for row in cursor.fetchall():
        print(row)
        
    conn.close()

if __name__ == "__main__":
    diag()
