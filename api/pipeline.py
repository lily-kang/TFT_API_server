from fastapi import APIRouter, HTTPException
from core.pipeline import batch_processor
from core.llm.syntax_fixer import syntax_fixer
from models.request import BatchPipelineRequest, MasterMetrics, ToleranceAbs, ToleranceRatio
from models.response import BatchPipelineResponse
from utils.logging import logger
from typing import Dict

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post(
    "/preview-prompt",
    summary="구문 수정 프롬프트 미리보기",
    description="LLM 호출 없이 구문 수정 프롬프트가 어떻게 구성되는지 미리 확인할 수 있습니다."
)
async def preview_syntax_prompt(
    text: str,
    master: MasterMetrics,
    tolerance_abs: ToleranceAbs,
    tolerance_ratio: ToleranceRatio,
    current_metrics: Dict[str, float],
    referential_clauses: str = ""
):
    """
    구문 수정 프롬프트 미리보기 엔드포인트
    
    Args:
        text: 수정할 텍스트
        master: 마스터 지표
        tolerance_abs: 절대값 허용 오차
        tolerance_ratio: 비율 허용 오차
        current_metrics: 현재 지표값들
        referential_clauses: 참조용 절 정보
        
    Returns:
        생성된 프롬프트 문자열
    """
    try:
        logger.info(f"프롬프트 미리보기 요청 수신: {len(text)} 글자")
        
        # 프롬프트 미리보기 실행
        prompt = await syntax_fixer.preview_prompt(
            text, master, tolerance_abs, tolerance_ratio, 
            current_metrics, referential_clauses
        )
        
        return {
            "prompt": prompt,
            "prompt_length": len(prompt),
            "text_length": len(text),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"프롬프트 미리보기 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"프롬프트 미리보기 중 오류가 발생했습니다: {str(e)}"
        )


@router.post(
    "/run-batch",
    response_model=BatchPipelineResponse,
    summary="배치 파이프라인 실행",
    description="여러 지문을 배치로 처리하여 구문/어휘 수정을 수행합니다."
)
async def run_batch_pipeline(request: BatchPipelineRequest):
    """
    배치 파이프라인 실행 엔드포인트
    
    여러 지문을 병렬로 처리하여 각각에 대해:
    1. 지표 분석 및 평가
    2. 필요 시 구문 수정
    3. 필요 시 어휘 수정
    4. 최종 결과 반환
    
    Args:
        request: 배치 처리 요청
        
    Returns:
        배치 처리 결과
    """
    try:
        logger.info(f"배치 파이프라인 요청 수신: {len(request.items)}개 항목")
        
        if not request.items:
            raise HTTPException(status_code=400, detail="처리할 항목이 없습니다")
        
        # 배치 처리 실행
        results = await batch_processor.process_batch(request.items)
        
        # 응답 생성
        response = BatchPipelineResponse(results=results)
        
        # 결과 통계 로깅
        success_count = sum(1 for r in results if r.status == "final")
        fail_count = len(results) - success_count
        logger.info(f"배치 처리 완료: 성공={success_count}, 실패={fail_count}")
        
        return response
        
    except Exception as e:
        logger.error(f"배치 파이프라인 실행 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"배치 파이프라인 실행 중 오류가 발생했습니다: {str(e)}"
        ) 