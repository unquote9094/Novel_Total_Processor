import json
import os
from typing import List, Dict, Tuple


class CheckpointManager:
    """
    요약 진행 상황을 저장하고 복구하는 클래스.
    """
    
    def __init__(self, file_path: str):
        """
        :param file_path: 원본 소설 파일 경로 (체크포인트 파일명 생성에 사용)
        """
        base, ext = os.path.splitext(file_path)
        self.checkpoint_file = f"{base}_checkpoint.json"
        self.original_file = file_path
    
    def save(self, completed_cids: List[int], results: Dict[int, str]):
        """
        진행 상황을 저장합니다.
        
        :param completed_cids: 완료된 챕터 ID 리스트
        :param results: {cid: summary} 형태의 결과 딕셔너리
        """
        checkpoint_data = {
            "original_file": self.original_file,
            "completed_cids": completed_cids,
            "results": results
        }
        
        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            print(f"[Checkpoint] Progress saved to {self.checkpoint_file}")
        except Exception as e:
            print(f"[Checkpoint] Error saving checkpoint: {e}")
    
    def load(self) -> Tuple[List[int], Dict[int, str]]:
        """
        저장된 진행 상황을 불러옵니다.
        
        :return: (완료된 챕터 ID 리스트, 결과 딕셔너리) 튜플
        """
        if not os.path.exists(self.checkpoint_file):
            print("[Checkpoint] No checkpoint file found. Starting fresh.")
            return [], {}
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            completed_cids = checkpoint_data.get("completed_cids", [])
            results = checkpoint_data.get("results", {})
            
            # JSON은 키를 문자열로 저장하므로 정수로 변환
            results = {int(k): v for k, v in results.items()}
            
            print(f"[Checkpoint] Loaded progress: {len(completed_cids)} chapters completed")
            return completed_cids, results
            
        except Exception as e:
            print(f"[Checkpoint] Error loading checkpoint: {e}")
            return [], {}
    
    def clear(self):
        """
        체크포인트 파일을 삭제합니다.
        """
        if os.path.exists(self.checkpoint_file):
            try:
                os.remove(self.checkpoint_file)
                print(f"[Checkpoint] Checkpoint file removed: {self.checkpoint_file}")
            except Exception as e:
                print(f"[Checkpoint] Error removing checkpoint: {e}")
    
    def exists(self) -> bool:
        """
        체크포인트 파일이 존재하는지 확인합니다.
        
        :return: 체크포인트 파일 존재 여부
        """
        return os.path.exists(self.checkpoint_file)
