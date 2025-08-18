"""유틸리티 헬퍼 함수들"""

from typing import Any, Dict, List, Optional
import asyncio
from utils.logging import logger


def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    딕셔너리에서 안전하게 값을 가져옵니다.
    
    Args:
        data: 대상 딕셔너리
        key: 키 이름
        default: 기본값
        
    Returns:
        값 또는 기본값
    """
    try:
        return data.get(key, default)
    except Exception:
        return default


def validate_metrics(metrics: Dict[str, float]) -> bool:
    """
    지표 데이터의 유효성을 검증합니다.
    
    Args:
        metrics: 지표 딕셔너리
        
    Returns:
        유효 여부
    """
    required_metrics = [
        "AVG_SENTENCE_LENGTH",
        "All_Embedded_Clauses_Ratio", 
        "CEFR_NVJD_A1A2_lemma_ratio"
    ]
    
    try:
        for metric in required_metrics:
            if metric not in metrics:
                logger.warning(f"필수 지표 누락: {metric}")
                return False
            
            value = metrics[metric]
            if not isinstance(value, (int, float)) or value < 0:
                logger.warning(f"잘못된 지표 값: {metric}={value}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"지표 검증 중 오류: {str(e)}")
        return False


def format_processing_time(start_time: float, end_time: float) -> str:
    """
    처리 시간을 포맷팅합니다.
    
    Args:
        start_time: 시작 시간
        end_time: 종료 시간
        
    Returns:
        포맷팅된 시간 문자열
    """
    try:
        duration = end_time - start_time
        
        if duration < 1:
            return f"{duration*1000:.0f}ms"
        elif duration < 60:
            return f"{duration:.1f}s"
        else:
            minutes = int(duration // 60)
            seconds = duration % 60
            return f"{minutes}m {seconds:.1f}s"
            
    except Exception:
        return "Unknown"


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    리스트를 지정된 크기로 분할합니다.
    
    Args:
        items: 분할할 리스트
        chunk_size: 청크 크기
        
    Returns:
        분할된 리스트들의 리스트
    """
    try:
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
    except Exception:
        return [items]


async def retry_async(
    func,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0
) -> Any:
    """
    비동기 함수 재시도 래퍼
    
    Args:
        func: 실행할 비동기 함수
        max_retries: 최대 재시도 횟수
        delay: 초기 대기 시간
        backoff_factor: 대기 시간 증가 배수
        
    Returns:
        함수 실행 결과
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries:
                wait_time = delay * (backoff_factor ** attempt)
                logger.warning(f"재시도 {attempt + 1}/{max_retries}: {wait_time:.1f}초 후 재시도")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"최대 재시도 횟수 초과: {str(e)}")
    
    raise last_exception


def sanitize_text(text: str) -> str:
    """
    텍스트를 정리합니다.
    
    Args:
        text: 원본 텍스트
        
    Returns:
        정리된 텍스트
    """
    try:
        if not text:
            return ""
        
        # 기본 정리
        cleaned = text.strip()
        
        # 연속된 공백 제거
        import re
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned
        
    except Exception:
        return text or "" 