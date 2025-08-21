import time
from fastapi import APIRouter, HTTPException
from core.pipeline import batch_processor
from core.services.text_processing_service import text_processing_service
from models.request import BatchPipelineRequest, SyntaxFixRequest, BatchSyntaxFixRequest
from models.response import BatchPipelineResponse, SyntaxFixResponse, BatchSyntaxFixResponse
from utils.logging import logger

router = APIRouter()


@router.post("/batch-pipeline", response_model=BatchPipelineResponse)
async def run_batch_pipeline(request: BatchPipelineRequest):
    """배치 파이프라인 실행"""
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


@router.post(
    "/syntax-fix",
    response_model=SyntaxFixResponse,
    summary="구문 수정 실행",
    description="단일 텍스트에 대해 구문 수정을 수행하고 단계별 진행 상황을 반환합니다."
)
async def fix_syntax(request: SyntaxFixRequest):
    """
    구문 수정 엔드포인트 (Service Layer 사용)
    
    Args:
        request: 구문 수정 요청
        
    Returns:
        단계별 구문 수정 결과
    """
    logger.info(f"구문 수정 요청 수신: request_id={request.request_id}, 텍스트={len(request.text)}글자")
    
    try:
        # Service Layer로 위임 (기존 로직 그대로)
        return await text_processing_service.fix_syntax_single(request)
    except Exception as e:
        logger.error(f"구문 수정 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"구문 수정 중 오류가 발생했습니다: {str(e)}"
        )


@router.post(
    "/batch-syntax-fix",
    response_model=BatchSyntaxFixResponse,
    summary="배치 구문 수정 실행",
    description="여러 텍스트를 병렬로 구문 수정합니다."
)
async def batch_fix_syntax(request: BatchSyntaxFixRequest):
    """
    배치 구문 수정 엔드포인트 (Service Layer 사용)
    
    Args:
        request: 배치 구문 수정 요청
        
    Returns:
        배치 구문 수정 결과
    """
    total_start_time = time.time()
    
    try:
        logger.info(f"배치 구문 수정 요청 수신: request_id={request.request_id}, 항목={len(request.items)}개")
        
        if not request.items:
            raise HTTPException(status_code=400, detail="처리할 항목이 없습니다")
        
        # Service Layer로 위임
        results = await text_processing_service.fix_syntax_batch(request.items, request.max_concurrent)
        
        # 결과 통계 계산
        total_time = time.time() - total_start_time
        successful_items = sum(1 for r in results if r.overall_success)
        failed_items = len(results) - successful_items
        overall_success = failed_items == 0
        
        # 응답 생성
        response = BatchSyntaxFixResponse(
            request_id=request.request_id,
            overall_success=overall_success,
            total_items=len(request.items),
            successful_items=successful_items,
            failed_items=failed_items,
            results=results,
            total_processing_time=total_time
        )
        
        # 결과 통계 로깅
        logger.info(f"배치 구문 수정 완료: 성공={successful_items}, 실패={failed_items}, 총시간={total_time:.2f}초")
        
        return response
        
    except Exception as e:
        total_time = time.time() - total_start_time
        error_msg = str(e)
        logger.error(f"배치 구문 수정 실행 실패: {error_msg}")
        
        return BatchSyntaxFixResponse(
            request_id=request.request_id,
            overall_success=False,
            total_items=len(request.items) if request.items else 0,
            successful_items=0,
            failed_items=len(request.items) if request.items else 0,
            results=[],
            total_processing_time=total_time,
            error_message=error_msg
        ) 