import os
from typing import Dict, Any
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# .env 파일 자동 로드
load_dotenv()


class Settings(BaseSettings):
    """애플리케이션 설정 관리"""
    
    # 외부 API 설정
    external_analyzer_api_url: str = "https://ils.jp.ngrok.io/api/enhanced_analyze"
    
    # OpenAI API 설정
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    
    # 앱 설정
    debug: bool = True
    log_level: str = "INFO"
    
    # 파이프라인 설정
    default_syntax_candidates: int = 3
    default_lexical_candidates: int = 3
    pipeline_timeout: int = 300
    
    # LLM 설정 - 구문 수정용 temperature (각 temperature별로 2개씩 생성)
    llm_temperatures: list = [0.2, 0.3]
    syntax_candidates_per_temperature: int = 2  # 각 temperature별 생성할 후보 수
    
    # 기본 허용 오차 설정
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