import sys
import argparse
import os
import asyncio
import traceback
import tkinter as tk
from tkinter import filedialog

# 모듈 인식을 위해 프로젝트 루트를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from novel_aize_ssr.ui_helper import UIHelper
from novel_aize_ssr.engine import NovelEngine

async def run_main():
    # 터미널 초기화 및 배너
    os.system('') 
    UIHelper.print_banner()

    parser = argparse.ArgumentParser(description="NovelAIze-SSR v3.0: High-Performance Novel Splitter & Summarizer")
    parser.add_argument("--input", "-i", type=str, help="Input novel text file path")
    parser.add_argument("--api-key", type=str, help="Google Gemini API Key")
    parser.add_argument("--format-only", "-f", action="store_true", help="Mode: Reformat and Save only")
    parser.add_argument("--summarize", "-s", action="store_true", help="Mode: AI Batch Summarize")
    parser.add_argument("--genre", "-g", type=str, default="general", choices=["fantasy", "sf", "romance", "general"])
    parser.add_argument("--output-format", "-o", type=str, default="plain", choices=["plain", "markdown", "json"])
    parser.add_argument("--resume", "-r", action="store_true", help="Resume from checkpoint")
    
    args = parser.parse_args()
    target_file = args.input

    # 1. 파일 선택 (GUI Fallback)
    if not target_file:
        UIHelper.print_warning("입력 파일이 지정되지 않았습니다. 파일 선택 창을 엽니다...")
        root = tk.Tk()
        root.withdraw()
        target_file = filedialog.askopenfilename(
            title="Select Novel Text File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        root.destroy()
        if not target_file:
            UIHelper.print_error("파일이 선택되지 않았습니다. 종료합니다.")
            return

    # 2. 파일 정보 출력
    if not os.path.exists(target_file):
        UIHelper.print_error(f"파일을 찾을 수 없습니다: {target_file}")
        return
    
    fsize_mb = os.path.getsize(target_file) / (1024 * 1024)
    est_chapters = int(os.path.getsize(target_file) / 7500)
    UIHelper.print_file_info(os.path.basename(target_file), fsize_mb, est_chapters)

    # 3. 모드 결정 (Interactive if not specified)
    mode = "preview"
    if args.format_only: mode = "format"
    elif args.summarize: mode = "summarize"
    else:
        UIHelper.print_info("사용할 모드를 선택해주세요:")
        UIHelper.print_info("  [1] 📝 서식 정리 (Reformat)")
        UIHelper.print_info("  [2] 🤖 AI 요약 (Summarize)")
        UIHelper.print_info("  [3] 👀 미리보기 (Preview)")
        
        try:
            choice = input("\n선택 (1-3) [Enter=3]: ").strip()
            if choice == "1": mode = "format"
            elif choice == "2": mode = "summarize"
            else: mode = "preview"
        except (EOFError, KeyboardInterrupt):
            print("\n취소되었습니다.")
            return

    # 4. 장르 결정 (Interactive for Summarize mode)
    genre = args.genre
    if mode == "summarize" and not any([args.genre != "general"]):
        UIHelper.print_info("\n소설의 장르를 선택해주세요:")
        genres = {"1": "general", "2": "fantasy", "3": "sf", "4": "romance"}
        for k, v in genres.items():
            print(f"  [{k}] {v.capitalize()}")
        
        g_choice = input("\n선택 (1-4) [Enter=1]: ").strip()
        genre = genres.get(g_choice, "general")

    # 5. 엔진 실행
    config_override = {}
    if args.api_key:
        config_override["api_key"] = args.api_key
        
    engine = NovelEngine(config_override=config_override)
    
    UIHelper.print_step_header(1, 1, f"Process started (Mode: {mode}, Genre: {genre})")
    
    try:
        results = await engine.run(
            input_path=target_file,
            mode=mode,
            genre=genre,
            output_format=args.output_format,
            resume=args.resume
        )
        
        if results.get("success"):
            if mode == "preview":
                UIHelper.print_success(f"미리보기 완료! 총 {results['total']}개 챕터 감지됨.")
                UIHelper.print_info("상위 5개 챕터 샘플:")
                for ch in results["chapters"]:
                    print(f"  - {ch.title}")
            else:
                UIHelper.print_completion(
                    output_file=results["output_file"],
                    total_chapters=results["total"],
                    total_time=results["total_time"],
                    speed=results["total"] / results["total_time"] if results["total_time"] > 0 else 0
                )
        else:
            UIHelper.print_error(results.get("error", "Unknown error during engine execution"))
            
    except Exception as e:
        UIHelper.print_error(f"시스템 오류 발생: {e}")
        if "--debug" in sys.argv:
            traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(run_main())
    except KeyboardInterrupt:
        print("\n\nUser interrupted. Exiting...")
        sys.exit(0)

