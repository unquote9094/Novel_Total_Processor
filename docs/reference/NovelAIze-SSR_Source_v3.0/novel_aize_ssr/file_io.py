import os
from typing import Iterator
from tqdm import tqdm
from novel_aize_ssr.structure import Chapter

def write_stream(chapters: Iterator[Chapter], output_path: str, total_chapters: int = None):
    """
    Chapter Stream을 받아 파일에 순차적으로 기록합니다.
    tqdm을 사용하여 진행 상황을 표시합니다.

    :param chapters: Chapter 객체를 Yield하는 Generator
    :param output_path: 저장할 파일 경로
    :param total_chapters: 전체 챕터 수 (tqdm 알고 있다면 표시용)
    """
    from novel_aize_ssr.reformatter import Reformatter
    
    reformatter = Reformatter()
    
    # tqdm은 iterator를 감싸서 자동 업데이트 가능
    # total을 모르면 개수 대신 처리된 속도만 나옴
    
    # 파일 쓰기 모드 ('w'는 덮어쓰기)
    with open(output_path, 'w', encoding='utf-8') as f:
        # PBar 설정
        pbar = tqdm(chapters, total=total_chapters, desc="Processing", unit="chap")
        
        chapter_count = 0
        char_count = 0
        
        for chapter in pbar:
            # 1. Beutify
            formatted_text = reformatter.beautify(chapter)
            
            # 2. Write
            f.write(formatted_text)
            
            # 3. Stats
            chapter_count += 1
            char_count += len(formatted_text)
            
            # PBar Description Update (Optional)
            if chapter_count % 10 == 0:
                pbar.set_postfix({"chars": f"{char_count/1024:.1f}KB"})

    print(f"\n[Done] Saved {chapter_count} chapters to: {output_path}")
