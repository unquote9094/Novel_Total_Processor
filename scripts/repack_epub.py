import os
import zipfile
import argparse

def pack_epub(folder_path, output_filename):
    """
    EPUB 폴더를 표준 규격에 맞게 재압축합니다.
    1. mimetype 파일을 압축 없이(Stored) 가장 먼저 추가해야 함.
    2. 나머지 파일은 압축하여 추가.
    """
    if not output_filename.endswith('.epub'):
        output_filename += '.epub'

    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as epub:
        # 1. mimetype 파일 처리 (반드시 첫 번째, 압축 없음)
        mimetype_path = os.path.join(folder_path, 'mimetype')
        if os.path.exists(mimetype_path):
            epub.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
        else:
            print("⚠️ mimetype 파일이 없습니다. 그래도 압축을 진행합니다.")

        # 2. 나머지 파일들 추가
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file == 'mimetype' and root == folder_path:
                    continue  # 이미 추가함
                
                file_path = os.path.join(root, file)
                # 폴더 내부의 상대 경로 계산
                arcname = os.path.relpath(file_path, folder_path)
                epub.write(file_path, arcname)

    print(f"✅ 성공: {output_filename} 생성이 완료되었습니다.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EPUB 폴더를 재압축합니다.")
    parser.add_argument("folder", help="압축할 EPUB 폴더 경로")
    parser.add_argument("output", help="저장할 파일명 (예: result.epub)")
    
    args = parser.parse_args()
    pack_epub(args.folder, args.output)
