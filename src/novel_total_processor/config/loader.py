"""설정 파일 로더 (YAML)

config.yml과 rules.yml을 읽어서 Python 객체로 변환
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from novel_total_processor.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PathsConfig:
    """경로 설정"""
    source_folders: List[str]
    output_folder: str
    database: str
    covers: str
    logs: str


@dataclass
class GeminiConfig:
    """Gemini API 설정"""
    model: str
    max_retries: int
    timeout: int
    rate_limit: int


@dataclass
class PerplexityConfig:
    """Perplexity API 설정"""
    search_model: str
    agent_model: str
    max_retries: int
    timeout: int
    rate_limit: int


@dataclass
class APIConfig:
    """API 설정"""
    gemini: GeminiConfig
    perplexity: PerplexityConfig


@dataclass
class ProcessingConfig:
    """처리 옵션"""
    max_workers: int
    batch_size: int
    duplicate_handling: str
    auto_detect_encoding: bool
    default_encoding: str


@dataclass
class EPUBConfig:
    """EPUB 생성 옵션"""
    version: int
    cover_size: Dict[str, int]
    css_template: str
    max_chars_per_chapter: int


@dataclass
class LoggingConfig:
    """로깅 설정"""
    file_level: str
    console_level: str
    retention_days: int


@dataclass
class UIConfig:
    """UI 설정"""
    theme: str
    progress_update_interval: int
    max_error_display: int


@dataclass
class Config:
    """전체 설정"""
    paths: PathsConfig
    api: APIConfig
    processing: ProcessingConfig
    epub: EPUBConfig
    logging: LoggingConfig
    ui: UIConfig


@dataclass
class FilenameRules:
    """파일명 규칙"""
    title: Dict[str, Any]
    episode: Dict[str, str]
    status: Dict[str, str]
    rating: Dict[str, Any]
    genre: Dict[str, Any]
    author: Dict[str, Any]
    tags: Dict[str, Any]
    filename: Dict[str, Any]


def load_config(config_path: str = "config/config.yml") -> Config:
    """config.yml 로드
    
    Args:
        config_path: 설정 파일 경로
    
    Returns:
        Config 객체
    
    Raises:
        FileNotFoundError: 설정 파일이 없을 때
        yaml.YAMLError: YAML 파싱 에러
    """
    path = Path(config_path)
    if not path.exists():
        logger.error(f"Config file not found: {config_path}")
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    logger.debug(f"Loading config from: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    config = Config(
        paths=PathsConfig(**data["paths"]),
        api=APIConfig(
            gemini=GeminiConfig(**data["api"]["gemini"]),
            perplexity=PerplexityConfig(**data["api"]["perplexity"])
        ),
        processing=ProcessingConfig(**data["processing"]),
        epub=EPUBConfig(**data["epub"]),
        logging=LoggingConfig(**data["logging"]),
        ui=UIConfig(**data["ui"])
    )
    
    logger.info(f"✅ Config loaded: {len(config.paths.source_folders)} source folders")
    return config


def load_rules(rules_path: str = "config/rules.yml") -> FilenameRules:
    """rules.yml 로드
    
    Args:
        rules_path: 규칙 파일 경로
    
    Returns:
        FilenameRules 객체
    
    Raises:
        FileNotFoundError: 규칙 파일이 없을 때
    """
    path = Path(rules_path)
    if not path.exists():
        logger.error(f"Rules file not found: {rules_path}")
        raise FileNotFoundError(f"Rules file not found: {rules_path}")
    
    logger.debug(f"Loading rules from: {rules_path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    rules = FilenameRules(
        title=data["title"],
        episode=data["episode"],
        status=data["status"],
        rating=data["rating"],
        genre=data["genre"],
        author=data["author"],
        tags=data["tags"],
        filename=data["filename"]
    )
    
    logger.info(f"✅ Rules loaded: {len(rules.genre['mapping'])} genre mappings")
    return rules


# 전역 설정 인스턴스 (싱글톤)
_config: Optional[Config] = None
_rules: Optional[FilenameRules] = None


def get_config() -> Config:
    """전역 설정 인스턴스 반환 (싱글톤)
    
    Returns:
        Config 객체
    
    Example:
        >>> from novel_total_processor.config.loader import get_config
        >>> config = get_config()
        >>> print(config.paths.database)
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_rules() -> FilenameRules:
    """전역 규칙 인스턴스 반환 (싱글톤)
    
    Returns:
        FilenameRules 객체
    """
    global _rules
    if _rules is None:
        _rules = load_rules()
    return _rules


def save_config(config: Config, config_path: str = "config/config.yml") -> None:
    """config.yml 저장
    
    Args:
        config: Config 객체
        config_path: 설정 파일 경로
    """
    path = Path(config_path)
    
    # Config 객체를 dict로 변환
    data = {
        "paths": {
            "source_folders": config.paths.source_folders,
            "output_folder": config.paths.output_folder,
            "database": config.paths.database,
            "covers": config.paths.covers,
            "logs": config.paths.logs
        },
        "api": {
            "gemini": {
                "model": config.api.gemini.model,
                "max_retries": config.api.gemini.max_retries,
                "timeout": config.api.gemini.timeout,
                "rate_limit": config.api.gemini.rate_limit
            },
            "perplexity": {
                "search_model": config.api.perplexity.search_model,
                "agent_model": config.api.perplexity.agent_model,
                "max_retries": config.api.perplexity.max_retries,
                "timeout": config.api.perplexity.timeout,
                "rate_limit": config.api.perplexity.rate_limit
            }
        },
        "processing": {
            "max_workers": config.processing.max_workers,
            "batch_size": config.processing.batch_size,
            "duplicate_handling": config.processing.duplicate_handling,
            "auto_detect_encoding": config.processing.auto_detect_encoding,
            "default_encoding": config.processing.default_encoding
        },
        "epub": {
            "version": config.epub.version,
            "cover_size": config.epub.cover_size,
            "css_template": config.epub.css_template,
            "max_chars_per_chapter": config.epub.max_chars_per_chapter
        },
        "logging": {
            "file_level": config.logging.file_level,
            "console_level": config.logging.console_level,
            "retention_days": config.logging.retention_days
        },
        "ui": {
            "theme": config.ui.theme,
            "progress_update_interval": config.ui.progress_update_interval,
            "max_error_display": config.ui.max_error_display
        }
    }
    
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    logger.info(f"✅ Config saved: {config_path}")

