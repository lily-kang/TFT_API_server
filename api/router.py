import time
from fastapi import APIRouter, HTTPException
from core.services.text_processing_service_v2 import text_processing_service
from models.request import SyntaxFixRequest, BatchSyntaxFixRequest
from models.response import SyntaxFixResponse, BatchSyntaxFixResponse
from models.internal import AnalyzerRequest
from core.analyzer import analyzer
from utils.logging import logger

router = APIRouter(tags=["revision"])


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
        
@router.post(
    "/analyze",
    summary="텍스트 지문 분석 요청",
    response_description="지문 분석 결과"
)
async def analyze_text(data: AnalyzerRequest):
    """
    제공된 텍스트를 외부 지문 분석기 API로 보내고, 그 결과를 반환합니다.
    """
    try:
        logger.info(f"텍스트 분석 요청: {len(data.text)} 글자")
        
        # 외부 분석기 API 호출
        result = await analyzer.analyze(data.text, data.include_syntax_analysis, data.llm_model)
        
        logger.info("텍스트 분석 완료")
        return result
        
    except Exception as e:
        logger.error(f"텍스트 분석 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"텍스트 분석 중 오류가 발생했습니다: {str(e)}"
        ) 

@router.post(
    "/revise",
    response_model=SyntaxFixResponse,
    summary="구문+어휘 결합 리비전 실행",
    description="구문 수정 후 결과를 분석하여 어휘 통과시 종료, 미통과시 어휘 단계로 분기합니다."
)
async def revise(request: SyntaxFixRequest):
    logger.info(f"결합 리비전 요청 수신: request_id={request.request_id}, 텍스트={len(request.text)}글자")
    try:
        return await text_processing_service.fix_revise_single(request)
    except Exception as e:
        logger.error(f"Revision 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"revision 중 오류: {str(e)}")


@router.post(
    "/batch-revise",
    response_model=BatchSyntaxFixResponse,
    summary="배치 결합 리비전 실행",
    description="여러 텍스트를 병렬로 결합 리비전합니다."
)
async def batch_revise(request: BatchSyntaxFixRequest):
    total_start_time = time.time()
    try:
        logger.info(f"배치 결합 리비전 요청 수신: request_id={request.request_id}, 항목={len(request.items)}개")
        if not request.items:
            raise HTTPException(status_code=400, detail="처리할 항목이 없습니다")
        results = await text_processing_service.fix_revise_batch(request.items, request.max_concurrent)
        total_time = time.time() - total_start_time
        successful_items = sum(1 for r in results if r.overall_success)
        failed_items = len(results) - successful_items
        overall_success = failed_items == 0
        response = BatchSyntaxFixResponse(
            request_id=request.request_id,
            overall_success=overall_success,
            total_items=len(request.items),
            successful_items=successful_items,
            failed_items=failed_items,
            results=results,
            total_processing_time=total_time
        )
        logger.info(f"배치 결합 리비전 완료: 성공={successful_items}, 실패={failed_items}, 총시간={total_time:.2f}초")
        return response
    except Exception as e:
        total_time = time.time() - total_start_time
        error_msg = str(e)
        logger.error(f"배치 결합 리비전 실패: {error_msg}")
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