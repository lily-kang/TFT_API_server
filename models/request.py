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

class SyntaxFixRequest(BaseModel):
    """구문 수정 요청 모델 (단순화된 버전)"""
    request_id: str = Field(description="요청 ID (앱스크립트에서 관리)")
    text: str = Field(description="수정할 텍스트") 
    master: MasterMetrics = Field(description="마스터 지표")
    referential_clauses: str = Field(default="", description="참조용 절 정보")




class BatchSyntaxFixRequest(BaseModel):
    """배치 구문 수정 요청 모델"""
    request_id: str = Field(description="배치 요청 ID")
    items: List[SyntaxFixRequest] = Field(description="구문 수정할 텍스트 리스트")
    max_concurrent: Optional[int] = Field(default=10, description="최대 동시 처리 개수 (기본값: 10)") 