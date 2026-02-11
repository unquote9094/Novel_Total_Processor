import json
import os
import re
from typing import Dict, Any, Optional

class ConfigManager:
    """
    config.json 및 prompts.txt를 통합 관리하는 클래스.
    설정 로드, 저장 및 장르별 프롬프트 추출을 담당합니다.
    """
    def __init__(self, config_file: str = "config.json", prompts_file: str = "prompts.txt"):
        self.config_file = config_file
        self.prompts_file_name = prompts_file
        self.prompts_file = self._resolve_prompts_path()
        
        self.default_config = {
            "api_key": "",
            "concurrency": 5,
            "request_delay": 2.0,
            "rate_limit_rpm": 15,
            "model_name": "gemini-3-flash-preview",
            "debug": False
        }
        self.config = self.load_config()
        self.prompts = self.load_prompts()

    def _resolve_prompts_path(self) -> str:
        # 1. Try CWD
        path = os.path.join(os.getcwd(), self.prompts_file_name)
        if os.path.exists(path):
            return path
        # 2. Try Package Dir
        return os.path.join(os.path.dirname(__file__), self.prompts_file_name)

    def load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_file):
            self.save_config(self.default_config)
            return self.default_config
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ConfigManager] Error loading config: {e}")
            return self.default_config

    def save_config(self, config: Dict[str, Any]):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"[ConfigManager] Error saving config: {e}")

    def load_prompts(self) -> Dict[str, Any]:
        prompts = {"summary": {}}
        if not os.path.exists(self.prompts_file):
            return prompts
        try:
            with open(self.prompts_file, 'r', encoding='utf-8') as f:
                content = f.read()
            sections = re.split(r'=== (.+) ===', content)
            for i in range(1, len(sections), 2):
                key = sections[i].strip()
                val = sections[i+1].strip()
                if key.startswith("summary_"):
                    genre = key.replace("summary_", "")
                    prompts["summary"][genre] = val
                else:
                    prompts[key] = val
            return prompts
        except Exception as e:
            print(f"[ConfigManager] Error loading prompts: {e}")
            return prompts

    def get_prompt(self, key: str, genre: Optional[str] = None) -> str:
        if key == "summary" and genre:
            return self.prompts.get("summary", {}).get(genre, self.prompts.get("summary", {}).get("general", ""))
        return self.prompts.get(key, "")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)
