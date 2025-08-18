import os
from typing import Dict, Any
from pydantic import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정 관리"""
    
    # 외부 API 설정
    external_analyzer_api_url: str = "https://ils.jp.ngrok.io/api/enhanced_analyze"
    
    # OpenAI API 설정
    openai_api_key: str = ""
    openai_model: str = "gpt-4"
    
    # 서버 설정
    debug: bool = True
    log_level: str = "INFO"
    
    # 파이프라인 설정
    default_syntax_candidates: int = 3
    default_lexical_candidates: int = 3
    pipeline_timeout: int = 300
    
    # LLM Temperature 설정
    llm_temperatures: list = [0.2, 0.3, 0.4]
    
    # 기본 tolerance 값
    default_tolerance_abs: Dict[str, float] = {
        "AVG_SENTENCE_LENGTH": 1.97
    }
    
    default_tolerance_ratio: Dict[str, float] = {
        "All_Embedded_Clauses_Ratio": 0.202,
        "CEFR_NVJD_A1A2_lemma_ratio": 0.104
    }
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 전역 설정 인스턴스
settings = Settings() 