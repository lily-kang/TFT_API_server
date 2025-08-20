from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class MasterMetrics(BaseModel):
    """마스터 지표 모델"""
    AVG_SENTENCE_LENGTH: float
    All_Embedded_Clauses_Ratio: float
    CEFR_NVJD_A1A2_lemma_ratio: float


class ToleranceAbs(BaseModel):
    """절대값 허용 오차 모델"""
    AVG_SENTENCE_LENGTH: float = Field(default=1.97)


class ToleranceRatio(BaseModel):
    """비율 허용 오차 모델"""
    All_Embedded_Clauses_Ratio: float = Field(default=0.202)
    CEFR_NVJD_A1A2_lemma_ratio: float = Field(default=0.104)


class PipelineItem(BaseModel):
    """파이프라인 처리 항목 모델"""
    client_id: str = Field(description="클라이언트 식별자 (행 번호, job_id 등)")
    original_text: str = Field(description="원본 텍스트")
    title: str = Field(description="지문 제목")
    generated_passage: str = Field(description="검수 대상 텍스트")
    include_syntax: bool = Field(default=True, description="구문 분석 포함 여부")
    master: MasterMetrics = Field(description="마스터 지표")
    tolerance_abs: Optional[ToleranceAbs] = Field(default=None, description="절대값 허용 오차")
    tolerance_ratio: Optional[ToleranceRatio] = Field(default=None, description="비율 허용 오차")
    syntax_candidates: int = Field(default=3, description="구문 수정 후보 개수")
    lexical_candidates: int = Field(default=3, description="어휘 수정 후보 개수")


class BatchPipelineRequest(BaseModel):
    """배치 파이프라인 요청 모델"""
    items: List[PipelineItem] = Field(description="처리할 항목 리스트")
    
    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {
                        "client_id": "row_12",
                        "original_text": "원문 A",
                        "title": "Story A",
                        "generated_passage": "검수대상 A",
                        "include_syntax": True,
                        "master": {
                            "AVG_SENTENCE_LENGTH": 12.3,
                            "All_Embedded_Clauses_Ratio": 0.18,
                            "CEFR_NVJD_A1A2_lemma_ratio": 0.46
                        },
                        "tolerance_abs": {"AVG_SENTENCE_LENGTH": 1.97},
                        "tolerance_ratio": {
                            "All_Embedded_Clauses_Ratio": 0.202,
                            "CEFR_NVJD_A1A2_lemma_ratio": 0.104
                        },
                        "syntax_candidates": 3,
                        "lexical_candidates": 3
                    }
                ]
            }
        } 


class SyntaxFixRequest(BaseModel):
    """구문 수정 요청 모델 (단순화된 버전)"""
    request_id: str = Field(description="요청 ID (앱스크립트에서 관리)")
    text: str = Field(description="수정할 텍스트")
    master: MasterMetrics = Field(description="마스터 지표")
    tolerance_abs: Optional[ToleranceAbs] = Field(default=None, description="절대값 허용 오차")
    tolerance_ratio: Optional[ToleranceRatio] = Field(default=None, description="비율 허용 오차")
    referential_clauses: str = Field(default="", description="참조용 절 정보")


# 사전 정의된 일반적인 참조 절 모음
DEFAULT_REFERENTIAL_CLAUSES = """
Noun Clauses: that they can visit, what people see, whether visitors come
Relative Clauses: which means they erupt, that form over time, where people live
Adverbial Clauses: when snow presses down, because it was cold, if you visit
Coordinate Clauses: and they love nature, but summers are mild, so people visit
""" 