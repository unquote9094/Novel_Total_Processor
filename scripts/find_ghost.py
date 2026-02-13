
import os
from pathlib import Path

TARGET_DIR = r"E:\DEVz\10_Novel_Total_Processor\Test_Novels\TEST"
TARGET_FILENAME_KEYWORD = "227화"  # 로그에 찍힌 키워드

print(f"Searching for files containing '{TARGET_FILENAME_KEYWORD}' in {TARGET_DIR}...")

found = False
for root, dirs, files in os.walk(TARGET_DIR):
    for file in files:
        if TARGET_FILENAME_KEYWORD in file:
            full_path = os.path.join(root, file)
            print(f"Found: {full_path}")
            found = True

if not found:
    print("File NOT found via Python os.walk().")
else:
    print("Search complete.")
