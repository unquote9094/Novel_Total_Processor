
import os
import re
from pathlib import Path
from datetime import datetime

# 설정
DATA_DIR = Path("data")
NOVEL_DIR = Path(r"E:\DEVz\10_Novel_Total_Processor\Test_Novels\TEST") # config.yml에서 읽은 경로

def find_latest_mapping_file():
    files = list(DATA_DIR.glob("mapping_result_*.txt"))
    if not files:
        print("No mapping files found.")
        return None
    
    # 시간순 정렬
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files[0]

def parse_mapping_file(file_path):
    mappings = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    old_name = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("="):
            continue
            
        if line.startswith("→"):
            new_name = line.replace("→", "").strip()
            if old_name:
                mappings.append((old_name, new_name))
                old_name = None
        else:
            old_name = line
            
    return mappings

def restore_filenames():
    mapping_file = find_latest_mapping_file()
    if not mapping_file:
        return
        
    print(f"Reading mapping file: {mapping_file}")
    mappings = parse_mapping_file(mapping_file)
    print(f"Found {len(mappings)} rename records.")
    
    restored_count = 0
    for old_name, new_name in mappings:
        # 확장자가 없는 old_name 처리 (매핑 파일에 확장자가 빠져있을 수 있음)
        if not old_name.endswith(".txt") and new_name.endswith(".txt"):
             old_name += ".txt"
             
        # 전체 경로
        current_path = NOVEL_DIR / new_name
        original_path = NOVEL_DIR / old_name
        
        if current_path.exists():
            try:
                print(f"Restoring: {new_name} -> {old_name}")
                current_path.rename(original_path)
                restored_count += 1
            except Exception as e:
                print(f"Failed to restore {new_name}: {e}")
        else:
            print(f"File not found: {new_name}")
            
    print(f"✅ Restored {restored_count} files.")

if __name__ == "__main__":
    restore_filenames()
