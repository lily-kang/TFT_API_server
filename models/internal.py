from typing import Dict, Optional, List
from pydantic import BaseModel
from dataclasses import dataclass


class AnalyzerRequest(BaseModel):
    """외부 분석기 API 요청 모델"""
    text: str
    auto_sentence_split: bool = True
    include_syntax_analysis: bool = True
    llm_model: str = "gpt-4.1"


class MetricsData(BaseModel):
    """추출된 지표 데이터"""
    AVG_SENTENCE_LENGTH: float
    All_Embedded_Clauses_Ratio: float
    CEFR_NVJD_A1A2_lemma_ratio: float
    # 어휘 수정을 위한 추가 필드들
    content_lemmas: Optional[int] = None
    propn_lemma_count: Optional[int] = None
    cefr_a1_NVJD_lemma_count: Optional[int] = None
    cefr_a2_NVJD_lemma_count: Optional[int] = None
    cefr_breakdown: Optional[Dict] = None
    sentence_count: Optional[int] = None
    lexical_tokens: Optional[int] = None
    total_clause_sentences: Optional[int] = None


class EvaluationResult(BaseModel):
    """지표 평가 결과"""
    syntax_pass: str  # "PASS" 또는 "FAIL"
    lexical_pass: str  # "PASS" 또는 "FAIL" 
    details: Dict[str, Dict]  # 지표별 상세 평가 결과


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
    index: int


class LLMResponse(BaseModel):
    """LLM 응답 모델"""
    candidates: List[LLMCandidate]
    selected_index: int
    selected_text: str 