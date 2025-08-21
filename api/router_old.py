from fastapi import APIRouter, HTTPException
from core.pipeline import batch_processor
from core.llm.syntax_fixer import syntax_fixer
from core.llm.prompt_builder import prompt_builder
from core.analyzer import analyzer
from core.metrics import metrics_extractor
from core.judge import judge
from core.services.text_processing_service import text_processing_service
from models.request import BatchPipelineRequest, MasterMetrics, ToleranceAbs, ToleranceRatio, SyntaxFixRequest, BatchSyntaxFixRequest
from models.response import BatchPipelineResponse, SyntaxFixResponse, StepResult, BatchSyntaxFixResponse
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
    description="단일 텍스트에 대해 구문 수정을 수행하고 단계별 진행 상황을 반환합니다. 앱스크립트에서 호출하기 쉽도록 단순화된 API입니다."
)
async def fix_syntax(request: SyntaxFixRequest):
    """
    구문 수정 엔드포인트 (단계별 진행 상황 포함)
    
    Args:
        request: 구문 수정 요청 (tolerance는 settings 기본값 사용)
        
    Returns:
        단계별 구문 수정 결과
    """
    total_start_time = time.time()
    step_results = []
    
    try:
        logger.info(f"구문 수정 요청 수신: request_id={request.request_id}, 텍스트={len(request.text)}글자")
        
        # settings에서 기본 허용 오차 사용
        from config.settings import settings
        tolerance_abs = ToleranceAbs()  # 기본값 사용
        tolerance_ratio = ToleranceRatio()  # 기본값 사용
        referential_clauses = request.referential_clauses 
        
        # 1단계: 원본 텍스트 분석
        step1_start_time = time.time()
        logger.info(f"[{request.request_id}] 1단계: 원본 텍스트 분석 시작")
        
        try:
            original_analysis = await analyzer.analyze(request.text, include_syntax=True)
            original_metrics = metrics_extractor.extract(original_analysis)
            original_evaluation = judge.evaluate(original_metrics, request.master, tolerance_abs, tolerance_ratio)
            
            # 원본 지표 딕셔너리 변환
            original_metrics_dict = {
                'AVG_SENTENCE_LENGTH': original_metrics.AVG_SENTENCE_LENGTH,
                'All_Embedded_Clauses_Ratio': original_metrics.All_Embedded_Clauses_Ratio,
                'CEFR_NVJD_A1A2_lemma_ratio': original_metrics.CEFR_NVJD_A1A2_lemma_ratio
            }
            
            # 문제 지표 자동 계산
            problematic_metric = prompt_builder.determine_problematic_metric(
                {
                    'avg_sentence_length': original_metrics.AVG_SENTENCE_LENGTH,
                    'embedded_clauses_ratio': original_metrics.All_Embedded_Clauses_Ratio
                },
                request.master, tolerance_abs, tolerance_ratio
            )
            
            if problematic_metric is None:
                # 문제가 있는 지표가 없으면 구문 수정 불필요
                step_results.append(StepResult(
                    step_name="어휘 수정",
                    success=False,
                    processing_time=0.0,
                    error_message="구문이 이미 통과하여 어휘 수정 단계 스킵"
                ))
                
                total_time = time.time() - total_start_time
                logger.info(f"[{request.request_id}] 구문 수정 불필요 (이미 통과)")
                
                return SyntaxFixResponse(
                    request_id=request.request_id,
                    overall_success=True,
                    original_text=request.text,
                    final_text=request.text,  # 원본과 동일
                    revision_success=True,
                    step_results=step_results,
                    original_metrics=original_metrics_dict,
                    final_metrics=original_metrics_dict,
                    candidates_generated=0,
                    candidates_passed=1,
                    total_processing_time=total_time
                )
            
            # 수정 문장 수 자동 계산
            # 목표 범위 계산
            if 'length' in problematic_metric.lower():
                target_min = request.master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                target_max = request.master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
                current_value = original_metrics.AVG_SENTENCE_LENGTH
            else:
                clause_tolerance = request.master.All_Embedded_Clauses_Ratio * tolerance_ratio.All_Embedded_Clauses_Ratio
                target_min = request.master.All_Embedded_Clauses_Ratio - clause_tolerance
                target_max = request.master.All_Embedded_Clauses_Ratio + clause_tolerance
                current_value = original_metrics.All_Embedded_Clauses_Ratio
            
            # 분석 결과에서 필요한 정보 추출 (metrics.py와 동일한 구조 사용)
            basic_overview = original_analysis.get("table_01_basic_overview", {})
            syntax_analysis = original_analysis.get("table_10_syntax_analysis", {})
            table_02 = original_analysis.get("table_02_detailed_tokens", {})
            
            sentence_count = basic_overview.get('sentence_count', 0)
            avg_sentence_length = basic_overview.get('avg_sentence_length', 0.0)
            lexical_tokens = table_02.get('lexical_tokens', 0)  # t2 테이블에서 가져오기
            
            analysis_result = {
                'sentence_count': sentence_count,
                'lexical_tokens': lexical_tokens,
                'adverbial_clause_sentences': syntax_analysis.get('adverbial_clause_sentences', 0),
                'coordinate_clause_sentences': syntax_analysis.get('coordinate_clause_sentences', 0),
                'nominal_clause_sentences': syntax_analysis.get('nominal_clause_sentences', 0),
                'relative_clause_sentences': syntax_analysis.get('relative_clause_sentences', 0)
            }
            
            num_modifications = prompt_builder.calculate_modification_count(
                request.text, problematic_metric, current_value, target_min, target_max, analysis_result
            )
            
            step1_time = time.time() - step1_start_time
            step_results.append(StepResult(
                step_name="원본 분석",
                success=True,
                processing_time=step1_time,
                details={
                    "syntax_pass": original_evaluation.syntax_pass,
                    "lexical_pass": original_evaluation.lexical_pass,
                    "metrics": original_metrics_dict
                }
            ))
            
            logger.info(f"[{request.request_id}] 1단계 완료 - 구문: {original_evaluation.syntax_pass}, 어휘: {original_evaluation.lexical_pass}")
            logger.info(f"[{request.request_id}] 자동 계산 결과 - 문제지표: {problematic_metric}, 수정문장수: {num_modifications}")
            
        except Exception as e:
            step1_time = time.time() - step1_start_time
            step_results.append(StepResult(
                step_name="원본 분석",
                success=False,
                processing_time=step1_time,
                error_message=str(e)
            ))
            raise e
        
        # 구문 수정이 필요한지 확인
        if original_evaluation.syntax_pass == "PASS":
            # 3단계: 어휘 수정 (스킵)
            step_results.append(StepResult(
                step_name="어휘 수정",
                success=False,
                processing_time=0.0,
                error_message="구문이 이미 통과하여 어휘 수정 단계 스킵"
            ))
            
            total_time = time.time() - total_start_time
            logger.info(f"[{request.request_id}] 구문 수정 불필요 (이미 통과)")
            
            return SyntaxFixResponse(
                request_id=request.request_id,
                overall_success=True,
                original_text=request.text,
                final_text=request.text,  # 원본과 동일
                revision_success=True,
                step_results=step_results,
                original_metrics=original_metrics_dict,
                final_metrics=original_metrics_dict,
                candidates_generated=0,
                candidates_passed=1,
                total_processing_time=total_time
            )
        
        # 2단계: 구문 수정 수행
        step2_start_time = time.time()
        logger.info(f"[{request.request_id}] 2단계: 구문 수정 시작")
        
        try:
            # 기존 fix_syntax 인터페이스를 새로운 요청 파라미터에 맞게 수정
            current_metrics_dict = {
                'AVG_SENTENCE_LENGTH': original_metrics.AVG_SENTENCE_LENGTH,
                'All_Embedded_Clauses_Ratio': original_metrics.All_Embedded_Clauses_Ratio,
                'CEFR_NVJD_A1A2_lemma_ratio': original_metrics.CEFR_NVJD_A1A2_lemma_ratio
            }
            
            # 새로운 수정된 fix_syntax 호출 (API에서 계산된 값 전달)
            candidates, selected_text, final_metrics, final_evaluation, total_candidates_generated = await syntax_fixer.fix_syntax_with_params(
                text=request.text,
                master=request.master,
                tolerance_abs=tolerance_abs,
                tolerance_ratio=tolerance_ratio,
                current_metrics=current_metrics_dict,
                num_modifications=num_modifications,
                problematic_metric=problematic_metric,
                referential_clauses=referential_clauses
            )
            
            # 최종 지표 딕셔너리 변환
            final_metrics_dict = {
                'AVG_SENTENCE_LENGTH': final_metrics.AVG_SENTENCE_LENGTH,
                'All_Embedded_Clauses_Ratio': final_metrics.All_Embedded_Clauses_Ratio,
                'CEFR_NVJD_A1A2_lemma_ratio': final_metrics.CEFR_NVJD_A1A2_lemma_ratio
            }
            
            step2_time = time.time() - step2_start_time
            syntax_success = final_evaluation.syntax_pass == "PASS"
            
            step_results.append(StepResult(
                step_name="구문 수정",
                success=syntax_success,
                processing_time=step2_time,
                details={
                    "candidates_generated": total_candidates_generated,
                    "candidates_passed": len(candidates),
                    "problematic_metric": problematic_metric,
                    "num_modifications": num_modifications,
                    "final_syntax_pass": final_evaluation.syntax_pass
                }
            ))
            
            logger.info(f"[{request.request_id}] 2단계 완료 - 성공: {syntax_success}, 후보: {len(candidates)}개")
            
        except Exception as e:
            step2_time = time.time() - step2_start_time
            step_results.append(StepResult(
                step_name="구문 수정",
                success=False,
                processing_time=step2_time,
                error_message=str(e)
            ))
            
            # 3단계: 어휘 수정 (실패로 스킵)
            step_results.append(StepResult(
                step_name="어휘 수정",
                success=False,
                processing_time=0.0,
                error_message="구문 수정 실패로 어휘 수정 단계 스킵"
            ))
            
            total_time = time.time() - total_start_time
            return SyntaxFixResponse(
                request_id=request.request_id,
                overall_success=False,
                original_text=request.text,
                final_text=None,
                revision_success=False,
                step_results=step_results,
                original_metrics=original_metrics_dict,
                final_metrics=None,
                candidates_generated=0,
                candidates_passed=0,
                total_processing_time=total_time,
                error_message=str(e)
            )
        
        # 3단계: 어휘 수정 (현재는 미구현)
        step_results.append(StepResult(
            step_name="어휘 수정",
            success=False,
            processing_time=0.0,
            error_message="어휘 수정은 현재 구현되지 않음"
        ))
        
        total_time = time.time() - total_start_time
        overall_success = final_evaluation.syntax_pass == "PASS"
        
        logger.info(f"[{request.request_id}] 전체 완료 - 성공: {overall_success}, 총 시간: {total_time:.2f}초")
        
        return SyntaxFixResponse(
            request_id=request.request_id,
            overall_success=overall_success,
            original_text=request.text,
            final_text=selected_text,
            revision_success=overall_success,
            step_results=step_results,
            original_metrics=original_metrics_dict,
            final_metrics=final_metrics_dict,
            candidates_generated=total_candidates_generated,
            candidates_passed=len(candidates),
            total_processing_time=total_time
        )
        
    except Exception as e:
        total_time = time.time() - total_start_time
        error_msg = str(e)
        logger.error(f"[{request.request_id}] 전체 실행 실패: {error_msg}")
        
        return SyntaxFixResponse(
            request_id=request.request_id,
            overall_success=False,
            original_text=request.text,
            final_text=None,
            revision_success=False,
            step_results=step_results,
            original_metrics=None,
            final_metrics=None,
            candidates_generated=0,
            candidates_passed=0,
            total_processing_time=total_time,
            error_message=error_msg
        ) 


@router.post(
    "/batch-syntax-fix",
    response_model=BatchSyntaxFixResponse,
    summary="배치 구문 수정 실행",
    description="여러 텍스트를 병렬로 구문 수정합니다. 동시 처리 개수를 제한하여 리소스를 효율적으로 관리합니다."
)
async def batch_fix_syntax(request: BatchSyntaxFixRequest):
    """
    배치 구문 수정 엔드포인트
    
    Args:
        request: 배치 구문 수정 요청
        
    Returns:
        배치 구문 수정 결과
    """
    total_start_time = time.time()
    
    try:
        logger.info(f"배치 구문 수정 요청 수신: request_id={request.request_id}, 항목={len(request.items)}개, 최대동시처리={request.max_concurrent}개")
        
        if not request.items:
            raise HTTPException(status_code=400, detail="처리할 항목이 없습니다")
        
        # 배치 구문 수정 실행
        batch_fixer = BatchSyntaxFixer(max_concurrent=request.max_concurrent)
        results = await batch_fixer.process_batch(request.items)
        
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