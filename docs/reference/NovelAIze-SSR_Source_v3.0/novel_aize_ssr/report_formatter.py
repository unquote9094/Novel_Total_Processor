import json
from typing import List, Dict
from novel_aize_ssr.structure import Chapter


class ReportFormatter:
    """
    요약 결과를 다양한 형식으로 출력하는 클래스.
    """
    
    def __init__(self, output_format: str = "plain"):
        """
        :param output_format: 출력 형식 (plain, markdown, json)
        """
        self.output_format = output_format
    
    def format(self, chapters: List[Chapter], results: Dict[int, str]) -> str:
        """
        지정된 형식으로 요약 결과를 포맷팅합니다.
        
        :param chapters: Chapter 객체 리스트
        :param results: {cid: summary} 형태의 결과 딕셔너리
        :return: 포맷팅된 문자열
        """
        if self.output_format == "markdown":
            return self.format_markdown(chapters, results)
        elif self.output_format == "json":
            return self.format_json(chapters, results)
        else:
            return self.format_plain(chapters, results)
    
    def format_plain(self, chapters: List[Chapter], results: Dict[int, str]) -> str:
        """
        일반 텍스트 형식으로 포맷팅합니다.
        """
        report = ["=== Novel Summary Report ===\n"]
        
        # CID(챕터 ID) 순으로 정렬하여 순서 보장
        sorted_chapters = sorted(chapters, key=lambda x: x.cid)
        
        for ch in sorted_chapters:
            summary = results.get(ch.cid, "(No Summary)")
            report.append(f"\n------------------------------------------------")
            report.append(f"[{ch.title}]")
            report.append(f"------------------------------------------------")
            report.append(f"{summary}\n")
            
        return "\n".join(report)
    
    def format_markdown(self, chapters: List[Chapter], results: Dict[int, str]) -> str:
        """
        마크다운 형식으로 포맷팅합니다.
        """
        report = ["# Novel Summary Report\n"]
        
        # CID(챕터 ID) 순으로 정렬하여 순서 보장
        sorted_chapters = sorted(chapters, key=lambda x: x.cid)
        
        for ch in sorted_chapters:
            summary = results.get(ch.cid, "(No Summary)")
            report.append(f"\n## {ch.title}\n")
            report.append(f"{summary}\n")
            report.append(f"---\n")
            
        return "\n".join(report)
    
    def format_json(self, chapters: List[Chapter], results: Dict[int, str]) -> str:
        """
        JSON 형식으로 포맷팅합니다.
        """
        # CID(챕터 ID) 순으로 정렬하여 순서 보장
        sorted_chapters = sorted(chapters, key=lambda x: x.cid)
        
        output = {
            "title": "Novel Summary Report",
            "total_chapters": len(sorted_chapters),
            "chapters": []
        }
        
        for ch in sorted_chapters:
            summary = results.get(ch.cid, "(No Summary)")
            output["chapters"].append({
                "cid": ch.cid,
                "title": ch.title,
                "length": ch.length,
                "summary": summary
            })
        
        return json.dumps(output, ensure_ascii=False, indent=2)
