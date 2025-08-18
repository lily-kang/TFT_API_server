"""커스텀 예외 클래스 정의"""


class PipelineError(Exception):
    """파이프라인 처리 중 발생하는 기본 예외"""
    pass


class AnalyzerAPIError(PipelineError):
    """외부 분석기 API 호출 실패 예외"""
    pass


class LLMAPIError(PipelineError):
    """LLM API 호출 실패 예외"""
    pass


class MetricsExtractionError(PipelineError):
    """지표 추출 실패 예외"""
    pass


class EvaluationError(PipelineError):
    """지표 평가 실패 예외"""
    pass


class TextProcessingError(PipelineError):
    """텍스트 처리 실패 예외"""
    pass 