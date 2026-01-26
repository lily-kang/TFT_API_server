import os
from typing import Dict
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# .env 파일 자동 로드
load_dotenv()


class Settings(BaseSettings):
    """애플리케이션 설정 관리"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # 외부 API 설정
    external_analyzer_api_url: str = "https://ils.jp.ngrok.io/api/enhanced_analyze"
    
    # OpenAI API 설정
    # Cloud Run에서는 Secret/Env로 주입되는 경우가 많아, 미설정 상태에서도 서버가 부팅되도록 Optional 허용
    # pydantic-settings에서 env var 이름 매핑은 `validation_alias`가 확실함
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4.1"
    
    # 앱 설정
    debug: bool = False
    log_level: str = "INFO"
    
    # 파이프라인 설정
    default_syntax_candidates: int = 3
    default_lexical_candidates: int = 3
    pipeline_timeout: int = 300
    
    # LLM 설정 - 구문 수정용 temperature (각 temperature별로 2개씩 생성)
    llm_temperatures: list = [0.2, 0.3]
    syntax_candidates_per_temperature: int = 2  # 각 temperature별 생성할 후보 수
    llm_max_output_tokens: int = 4096
    
    # 기본 허용 오차 설정
    default_tolerance_abs: Dict[str, float] = {
        "AVG_SENTENCE_LENGTH": 1.97
    }
    default_tolerance_ratio: Dict[str, float] = {
        "All_Embedded_Clauses_Ratio": 0.202,
        "CEFR_NVJD_A1A2_lemma_ratio": 0.104
    }
    
# 전역 설정 인스턴스
settings = Settings() 