from typing import Dict, Optional, List
from pydantic import BaseModel
from dataclasses import dataclass


class AnalyzerRequest(BaseModel):
    """외부 분석기 API 요청 모델"""
    text: str
    auto_sentence_split: bool = True
    include_syntax_analysis: bool = True


class MetricsData(BaseModel):
    """추출된 지표 데이터"""
    AVG_SENTENCE_LENGTH: float
    All_Embedded_Clauses_Ratio: float
    CEFR_NVJD_A1A2_lemma_ratio: float
    # 기타 지표들도 포함할 수 있음
    AVG_CONTENT_SYLLABLES: Optional[float] = None
    CL_CEFR_B1B2C1C2_ratio: Optional[float] = None
    PP_Weighted_Ratio: Optional[float] = None


class EvaluationResult(BaseModel):
    """지표 평가 결과"""
    syntax_pass: str  # "PASS" or "FAIL"
    lexical_pass: str  # "PASS" or "FAIL"
    detailed_metrics: Dict[str, Dict]  # 지표별 상세 정보
    

@dataclass
class ToleranceRange:
    """허용 오차 범위"""
    min_value: float
    max_value: float
    
    def is_within_range(self, value: float) -> bool:
        """값이 허용 범위 내에 있는지 확인"""
        return self.min_value <= value <= self.max_value


class LLMCandidate(BaseModel):
    """LLM 생성 후보"""
    text: str
    temperature: float
    reasoning: Optional[str] = None


class LLMResponse(BaseModel):
    """LLM 응답 모델"""
    candidates: List[LLMCandidate]
    selected_index: int
    selected_text: str 