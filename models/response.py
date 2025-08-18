from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class StatusEnum(str, Enum):
    """파이프라인 처리 상태"""
    FINAL = "final"
    SYNTAX_FAIL = "syntax_fail"
    LEXICAL_FAIL = "lexical_fail"
    ERROR = "error"


class PassEnum(str, Enum):
    """통과/실패 상태"""
    PASS = "PASS"
    FAIL = "FAIL"


class AttemptCounts(BaseModel):
    """시도 횟수 모델"""
    syntax: int = Field(default=0, description="구문 수정 시도 횟수")
    lexical: int = Field(default=0, description="어휘 수정 시도 횟수")


class TraceStep(BaseModel):
    """처리 과정 추적 모델"""
    step: str = Field(description="처리 단계명")
    metrics: Optional[Dict[str, float]] = Field(default=None, description="분석 지표")
    syntax_pass: Optional[str] = Field(default=None, description="구문 통과 여부")
    lexical_pass: Optional[str] = Field(default=None, description="어휘 통과 여부")
    candidates: Optional[List[str]] = Field(default=None, description="후보 텍스트들")
    selected: Optional[str] = Field(default=None, description="선택된 텍스트")
    error: Optional[str] = Field(default=None, description="에러 메시지")


class PipelineResult(BaseModel):
    """파이프라인 처리 결과 모델"""
    client_id: str = Field(description="클라이언트 식별자")
    status: StatusEnum = Field(description="최종 처리 상태")
    syntax_pass: PassEnum = Field(description="구문 지표 통과 여부")
    lexical_pass: PassEnum = Field(description="어휘 지표 통과 여부")
    detailed_result: str = Field(description="상세 분석 결과")
    final_text: Optional[str] = Field(default=None, description="최종 텍스트")
    attempts: AttemptCounts = Field(description="시도 횟수")
    trace: Optional[List[TraceStep]] = Field(default=None, description="처리 과정 추적")
    error_message: Optional[str] = Field(default=None, description="에러 메시지")


class BatchPipelineResponse(BaseModel):
    """배치 파이프라인 응답 모델"""
    results: List[PipelineResult] = Field(description="처리 결과 리스트")
    
    class Config:
        schema_extra = {
            "example": {
                "results": [
                    {
                        "client_id": "row_12",
                        "status": "final",
                        "syntax_pass": "PASS",
                        "lexical_pass": "PASS",
                        "detailed_result": "AVG_SENTENCE_LENGTH: 10.470 vs [6.620 ~ 11.080] → Pass\nCEFR_NVJD_A1A2_lemma_ratio: 0.571 vs [0.515 ~ 0.651] → Pass",
                        "final_text": "최종 텍스트 A",
                        "attempts": {"syntax": 1, "lexical": 1},
                        "trace": []
                    }
                ]
            }
        } 