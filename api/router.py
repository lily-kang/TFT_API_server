from fastapi import APIRouter, HTTPException
from core.pipeline import batch_processor
from core.llm.syntax_fixer import syntax_fixer
from core.analyzer import analyzer
from core.metrics import metrics_extractor
from core.judge import judge
from models.request import BatchPipelineRequest, MasterMetrics, ToleranceAbs, ToleranceRatio, SyntaxFixRequest, DEFAULT_REFERENTIAL_CLAUSES
from models.response import BatchPipelineResponse, SyntaxFixResponse
from utils.logging import logger
from typing import Dict
import time

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


@router.post(
    "/syntax-fix",
    response_model=SyntaxFixResponse,
    summary="구문 수정 실행",
    description="단일 텍스트에 대해 구문 수정을 수행하고 결과를 반환합니다. 앱스크립트에서 호출하기 쉽도록 단순화된 API입니다."
)
async def fix_syntax(request: SyntaxFixRequest):
    """
    구문 수정 엔드포인트
    
    Args:
        request: 구문 수정 요청
        
    Returns:
        구문 수정 결과
    """
    start_time = time.time()
    
    try:
        logger.info(f"구문 수정 요청 수신: request_id={request.request_id}, 텍스트={len(request.text)}글자")
        
        # 기본값 설정
        tolerance_abs = request.tolerance_abs or ToleranceAbs()
        tolerance_ratio = request.tolerance_ratio or ToleranceRatio()
        referential_clauses = request.referential_clauses or DEFAULT_REFERENTIAL_CLAUSES
        
        # 1단계: 원본 텍스트 분석
        logger.info(f"[{request.request_id}] 원본 텍스트 분석 시작")
        original_analysis = await analyzer.analyze(request.text, include_syntax=True)
        original_metrics = metrics_extractor.extract(original_analysis)
        original_evaluation = judge.evaluate(original_metrics, request.master, tolerance_abs, tolerance_ratio)
        
        # 원본 지표 딕셔너리 변환
        original_metrics_dict = {
            'AVG_SENTENCE_LENGTH': original_metrics.AVG_SENTENCE_LENGTH,
            'All_Embedded_Clauses_Ratio': original_metrics.All_Embedded_Clauses_Ratio,
            'CEFR_NVJD_A1A2_lemma_ratio': original_metrics.CEFR_NVJD_A1A2_lemma_ratio
        }
        
        logger.info(f"[{request.request_id}] 원본 분석 완료 - 구문: {original_evaluation.syntax_pass}, 어휘: {original_evaluation.lexical_pass}")
        
        # 구문 수정이 필요한지 확인
        if original_evaluation.syntax_pass == "PASS":
            processing_time = time.time() - start_time
            logger.info(f"[{request.request_id}] 구문 수정 불필요 (이미 통과)")
            
            return SyntaxFixResponse(
                request_id=request.request_id,
                success=True,
                original_text=request.text,
                fixed_text=request.text,  # 원본과 동일
                original_metrics=original_metrics_dict,
                fixed_metrics=original_metrics_dict,
                candidates_generated=0,
                candidates_passed=1,
                processing_time=processing_time
            )
        
        # 2단계: 구문 수정 수행
        logger.info(f"[{request.request_id}] 구문 수정 시작")
        current_metrics_dict = {
            'AVG_SENTENCE_LENGTH': original_metrics.AVG_SENTENCE_LENGTH,
            'All_Embedded_Clauses_Ratio': original_metrics.All_Embedded_Clauses_Ratio,
            'CEFR_NVJD_A1A2_lemma_ratio': original_metrics.CEFR_NVJD_A1A2_lemma_ratio
        }
        
        # 구문 수정 실행
        candidates, selected_text, final_metrics, final_evaluation = await syntax_fixer.fix_syntax(
            text=request.text,
            master=request.master,
            tolerance_abs=tolerance_abs,
            tolerance_ratio=tolerance_ratio,
            current_metrics=current_metrics_dict,
            referential_clauses=referential_clauses
        )
        
        # 최종 지표 딕셔너리 변환
        final_metrics_dict = {
            'AVG_SENTENCE_LENGTH': final_metrics.AVG_SENTENCE_LENGTH,
            'All_Embedded_Clauses_Ratio': final_metrics.All_Embedded_Clauses_Ratio,
            'CEFR_NVJD_A1A2_lemma_ratio': final_metrics.CEFR_NVJD_A1A2_lemma_ratio
        }
        
        processing_time = time.time() - start_time
        success = final_evaluation.syntax_pass == "PASS"
        
        logger.info(f"[{request.request_id}] 구문 수정 완료 - 성공: {success}, 후보: {len(candidates)}개, 시간: {processing_time:.2f}초")
        
        return SyntaxFixResponse(
            request_id=request.request_id,
            success=success,
            original_text=request.text,
            fixed_text=selected_text,
            original_metrics=original_metrics_dict,
            fixed_metrics=final_metrics_dict,
            candidates_generated=len(candidates),
            candidates_passed=1 if success else 0,
            processing_time=processing_time
        )
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = str(e)
        logger.error(f"[{request.request_id}] 구문 수정 실패: {error_msg}")
        
        return SyntaxFixResponse(
            request_id=request.request_id,
            success=False,
            original_text=request.text,
            fixed_text=None,
            original_metrics=None,
            fixed_metrics=None,
            candidates_generated=0,
            candidates_passed=0,
            processing_time=processing_time,
            error_message=error_msg
        ) 