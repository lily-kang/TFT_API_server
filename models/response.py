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


class StepResult(BaseModel):
    """단계별 처리 결과 모델"""
    step_name: str = Field(description="단계명")
    success: bool = Field(description="성공 여부")
    processing_time: float = Field(description="처리 시간 (초)")
    details: Optional[Dict[str, Any]] = Field(default=None, description="상세 정보")
    error_message: Optional[str] = Field(default=None, description="에러 메시지")


class SyntaxFixResponse(BaseModel):
    """구문 수정 응답 모델 (단계별 진행 상황 포함)"""
    request_id: str = Field(description="요청 ID")
    overall_success: bool = Field(description="전체 성공 여부")
    
    # 최종 결과
    original_text: str = Field(description="원본 텍스트")
    final_text: Optional[str] = Field(default=None, description="최종 수정된 텍스트")
    revision_success: bool = Field(default=False, description="최종 수정 성공 여부")
    
    # 단계별 결과 (1단계: 원본 분석, 2단계: 구문 수정, 3단계: 어휘 수정)
    step_results: List[StepResult] = Field(description="단계별 처리 결과")
    
    # 지표 정보
    original_metrics: Optional[Dict[str, float]] = Field(default=None, description="원본 지표")
    final_metrics: Optional[Dict[str, float]] = Field(default=None, description="최종 지표")
    
    # 처리 정보
    candidates_generated: int = Field(default=0, description="생성된 후보 수")
    candidates_passed: int = Field(default=0, description="통과한 후보 수")
    total_processing_time: float = Field(description="총 처리 시간 (초)")
    
    # 에러 정보
    error_message: Optional[str] = Field(default=None, description="전체 에러 메시지")
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "req_123",
                "overall_success": True,
                "original_text": "원본 텍스트입니다.",
                "final_text": "수정된 텍스트입니다.",
                "revision_success": True,
                "step_results": [
                    {
                        "step_name": "원본 분석",
                        "success": True,
                        "processing_time": 2.5,
                        "details": {"syntax_pass": "FAIL", "lexical_pass": "PASS"}
                    },
                    {
                        "step_name": "구문 수정",
                        "success": True,
                        "processing_time": 15.3,
                        "details": {"candidates_generated": 4, "candidates_passed": 2}
                    },
                    {
                        "step_name": "어휘 수정",
                        "success": False,
                        "processing_time": 0.0,
                        "error_message": "어휘 수정은 현재 구현되지 않음"
                    }
                ],
                "candidates_generated": 4,
                "candidates_passed": 2,
                "total_processing_time": 17.8
            }
        } 


class BatchSyntaxFixResponse(BaseModel):
    """배치 구문 수정 응답 모델"""
    request_id: str = Field(description="배치 요청 ID")
    overall_success: bool = Field(description="전체 성공 여부")
    total_items: int = Field(description="총 처리 항목 수")
    successful_items: int = Field(description="성공한 항목 수")
    failed_items: int = Field(description="실패한 항목 수")
    results: List[SyntaxFixResponse] = Field(description="각 항목별 처리 결과")
    total_processing_time: float = Field(description="총 처리 시간 (초)")
    error_message: Optional[str] = Field(default=None, description="전체 에러 메시지") 