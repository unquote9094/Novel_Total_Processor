import json
import os
from typing import Dict, Any

CONFIG_FILE = "config.json"
# 1. Try Config Directory (Dev) or CWD (Prod)
PROMPTS_FILE_NAME = "prompts.txt"
PROMPTS_FILE = os.path.join(os.getcwd(), PROMPTS_FILE_NAME)

# 2. Fallback to package dir (if not found in CWD)
if not os.path.exists(PROMPTS_FILE):
    PROMPTS_FILE = os.path.join(os.path.dirname(__file__), PROMPTS_FILE_NAME)

DEFAULT_CONFIG = {
    "api_key": "",
    "concurrency": 5,
    "request_delay": 2.0,
    "rate_limit_rpm": 15,
    "model_name": "gemini-3-flash-preview",
    "debug": False
}

def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json.
    If file doesn't exist, create it with default values.
    """
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Config] Error loading config.json: {e}")
        return DEFAULT_CONFIG

def save_config(config: Dict[str, Any]):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        print(f"[Config] Default configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"[Config] Error saving config: {e}")

def load_prompts() -> Dict[str, Any]:
    """
    Load prompts from the single 'prompts.txt' file.
    Content is separated by '=== key ==='.
    """
    prompts = {"summary": {}}
    
    if not os.path.exists(PROMPTS_FILE):
        print(f"[Config] Warning: Prompts file not found at {PROMPTS_FILE}")
        return {}
    
    try:
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            
        import re
        # Split by separator: === key ===
        # re.split will return [text_before_first, key1, val1, key2, val2, ...]
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
        print(f"[Config] Error loading prompts from file: {e}")
        return {}

def get_prompt(genre: str = "general") -> str:
    """
    Get the summary prompt for the specified genre.
    
    :param genre: Genre type (fantasy, sf, romance, general)
    :return: Prompt string for the genre
    """
    prompts = load_prompts()
    summary_prompts = prompts.get("summary", {})
    
    # Default to general if genre not found
    if genre not in summary_prompts:
        genre = "general"
    
    return summary_prompts.get(genre, "")
