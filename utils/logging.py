import logging
import sys
from typing import Optional
from config.settings import settings


def setup_logging(
    level: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    로깅 설정을 초기화합니다.
    
    Args:
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: 로그 포맷 문자열
        
    Returns:
        설정된 로거 인스턴스
    """
    if level is None:
        level = settings.log_level
        
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 로거 설정
    logger = logging.getLogger("pipeline_api")
    logger.setLevel(getattr(logging, level.upper()))
    
    # 핸들러가 이미 있다면 제거 (중복 방지)
    if logger.handlers:
        logger.handlers.clear()
    
    # 콘솔 핸들러 추가
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    # 포매터 설정
    formatter = logging.Formatter(format_string)
    console_handler.setFormatter(formatter)
    
    # 핸들러를 로거에 추가
    logger.addHandler(console_handler)
    
    return logger


# 전역 로거 인스턴스
logger = setup_logging() 