"""
Legacy 텍스트 처리 서비스

⚠️ 주의: 이 파일은 현재 사용되지 않습니다.
- 현재 사용 중인 서비스: text_processing_service_v2.py
- 이 파일은 참고용으로 보관되어 있습니다.

포함된 메서드:
- fix_syntax_single: 단일 텍스트 구문 수정 (구문만)
- fix_syntax_batch: 배치 구문 수정 (구문만)

현재 API 엔드포인트:
- /revise → text_processing_service_v2.fix_revise_single (구문+어휘 통합)
- /batch-revise → text_processing_service_v2.fix_revise_batch (구문+어휘 통합)
"""

import time
import asyncio
from typing import List, Dict, Any
from models.request import SyntaxFixRequest, ToleranceAbs, ToleranceRatio
from models.response import SyntaxFixResponse, StepResult
from core.analyzer import analyzer
from core.metrics import metrics_extractor
from core.judge import judge
from core.llm.syntax_fixer import syntax_fixer
from core.llm.prompt_builder import prompt_builder
from utils.logging import logger


class TextProcessingService:
    """
    [DEPRECATED] 텍스트 처리 서비스 (구문 수정만)
    
    ⚠️ 이 서비스는 더 이상 사용되지 않습니다.
    대신 text_processing_service_v2.TextProcessingServiceV2를 사용하세요.
    """
    
    def __init__(self):
        self.max_concurrent = 10  # 기본 배치 동시 처리 개수
    
    async def fix_syntax_single(self, request: SyntaxFixRequest) -> SyntaxFixResponse:
        """
        [DEPRECATED] 단일 텍스트 구문 수정 (구문만)
        
        ⚠️ 이 메서드는 더 이상 사용되지 않습니다.
        대신 text_processing_service_v2.fix_revise_single을 사용하세요.
        
        Args:
            request: 구문 수정 요청
            
        Returns:
            구문 수정 결과 (구문만, 어휘 수정 없음)
        """
        total_start_time = time.time()
        step_results = []
        
        try:
            logger.info(f"Text Revision Start: request_id={request.request_id}, Text={len(request.text)}글자")
            
            # settings에서 기본 허용 오차 사용
            tolerance_abs = ToleranceAbs()  # 기본값 사용
            tolerance_ratio = ToleranceRatio()  # 기본값 사용
            referential_clauses = request.referential_clauses or ""
            
            #### 1단계: 텍스트 분석
            step1_start_time = time.time()
            logger.info(f"[{request.request_id}] 1단계: 요청 텍스트 분석 시작")
            
            try:
                original_analysis = await analyzer.analyze(request.text, include_syntax=True)
                # 구문 수정에 필요한 지표들만 가져오는 메서드 
                original_metrics = metrics_extractor.extract(original_analysis)
                original_evaluation = judge.evaluate(original_metrics, request.master, tolerance_abs, tolerance_ratio)
                
                # 원본 텍스트 지표 딕셔너리 변환
                original_metrics_dict = {
                    'AVG_SENTENCE_LENGTH': original_metrics.AVG_SENTENCE_LENGTH,
                    'All_Embedded_Clauses_Ratio': original_metrics.All_Embedded_Clauses_Ratio,
                    'CEFR_NVJD_A1A2_lemma_ratio': original_metrics.CEFR_NVJD_A1A2_lemma_ratio
                }
                
                step1_time = time.time() - step1_start_time
                step_results.append(StepResult(
                    step_name="원본 지문 분석",
                    status=f"[revise] 원본 분석 완료 - 구문: {original_evaluation.syntax_pass}, 어휘: {original_evaluation.lexical_pass}",
                    success=True,
                    processing_time=step1_time,
                    details={
                        "syntax_pass": original_evaluation.syntax_pass,
                        "lexical_pass": original_evaluation.lexical_pass,
                        "details": original_evaluation.details
                    }
                ))
                
                logger.info(f"[{request.request_id}] 1단계 완료 - 구문 통과?: {original_evaluation.syntax_pass}, 어휘 통과?: {original_evaluation.lexical_pass}")
                
            except Exception as e:
                step1_time = time.time() - step1_start_time
                step_results.append(StepResult(
                    step_name="원본 지문 분석",
                    status=f"[revise] 원본 분석 실패 - {str(e)}",
                    success=False,
                    processing_time=step1_time,
                    error_message=str(e)
                ))
                raise e
            
            # 구문 수정 필요한지 확인
            if original_evaluation.syntax_pass == "PASS" :
                # 구문 통과하면 종료
                total_time = time.time() - total_start_time
                logger.info(f"[{request.request_id}] 구문 통과하여 종료")
                return SyntaxFixResponse(
                    request_id=request.request_id,
                    overall_success=True,
                    original_text=request.text,
                    final_text=request.text,  # 원본과 동일
                    revision_success=True,
                    step_results=step_results,
                    original_metrics=original_metrics_dict,
                    final_metrics=original_metrics_dict, #원본과 동일
                    candidates_generated=0,
                    candidates_passed=0,
                    total_processing_time=total_time
                )
            
            ##### 2단계: 구문 미통과시 구문 수정 수행
            step2_start_time = time.time()
            logger.info(f"[{request.request_id}] 2단계: 구문 수정 시작")
            
            try:
                # 문제 지표 자동 계산
                logger.info(f"[{request.request_id}] 문제 지표 계산 시작")
                logger.info(f"[{request.request_id}] 현재 지표: avg_sentence_length={original_metrics.AVG_SENTENCE_LENGTH:.3f}, embedded_clauses_ratio={original_metrics.All_Embedded_Clauses_Ratio:.3f}")
                logger.info(f"[{request.request_id}] 마스터 지표: avg_sentence_length={request.master.AVG_SENTENCE_LENGTH:.3f}, embedded_clauses_ratio={request.master.All_Embedded_Clauses_Ratio:.3f}")

                problematic_metric = prompt_builder.determine_problematic_metric(
                    {
                        'avg_sentence_length': original_metrics.AVG_SENTENCE_LENGTH,
                        'embedded_clauses_ratio': original_metrics.All_Embedded_Clauses_Ratio
                    },
                    request.master, tolerance_abs, tolerance_ratio
                )
                
                logger.info(f"[{request.request_id}] 문제 지표 결과: {problematic_metric}")
                 
                # 수정 문장 수 자동 계산
                # 목표 범위 계산
                if problematic_metric == "avg_sentence_length":
                    target_min = request.master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                    target_max = request.master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
                    current_value = original_metrics.AVG_SENTENCE_LENGTH
                else:
                    target_min = request.master.All_Embedded_Clauses_Ratio - tolerance_ratio.All_Embedded_Clauses_Ratio
                    target_max = request.master.All_Embedded_Clauses_Ratio + tolerance_ratio.All_Embedded_Clauses_Ratio
                    current_value = original_metrics.All_Embedded_Clauses_Ratio
                
                # 구문 수정용 분석 결과
                analysis_result = {
                    'sentence_count': original_metrics.sentence_count,
                    'lexical_tokens': original_metrics.lexical_tokens,
                    'total_clause_sentences': original_metrics.total_clause_sentences
                }
                
                logger.info(f"[{request.request_id}] 수정 문장 수 계산 시작")
                logger.info(f"[{request.request_id}] problematic_metric: {problematic_metric}")
                logger.info(f"[{request.request_id}] current_value: {current_value:.3f}")
                logger.info(f"[{request.request_id}] target_min: {target_min:.3f}, target_max: {target_max:.3f}")
                logger.info(f"[{request.request_id}] analysis_result: {analysis_result}")
                
                modification_params = prompt_builder.calculate_modification_count(
                    problematic_metric, current_value, target_min, target_max, analysis_result
                )
                
                num_modifications = modification_params['num_modifications']
                prompt_type = modification_params['prompt_type']
                
                logger.info(f"[{request.request_id}] 계산된 수정 문장 수: {num_modifications}")
                logger.info(f"[{request.request_id}] 선택된 프롬프트 타입: {prompt_type}")
                
                avg_target_min = request.master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                avg_target_max = request.master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
                clause_target_min = request.master.All_Embedded_Clauses_Ratio - tolerance_ratio.All_Embedded_Clauses_Ratio
                clause_target_max = request.master.All_Embedded_Clauses_Ratio + tolerance_ratio.All_Embedded_Clauses_Ratio
                
                # fix_syntax_with_params 호출 (계산된 값 전달)
                candidates, selected_text, final_metrics, final_evaluation, total_candidates_generated = await syntax_fixer.fix_syntax_with_params(
                    text=request.text,
                    avg_target_min=avg_target_min,
                    avg_target_max=avg_target_max,
                    clause_target_min=clause_target_min,
                    clause_target_max=clause_target_max,
                    current_metrics=original_metrics_dict,
                    num_modifications=num_modifications,
                    problematic_metric=problematic_metric,
                    referential_clauses=referential_clauses,
                    prompt_type=prompt_type
                )
                
                # 최종 지표 딕셔너리 변환
                final_metrics_dict = {
                    'AVG_SENTENCE_LENGTH': final_metrics.get('AVG_SENTENCE_LENGTH', 0),
                    'All_Embedded_Clauses_Ratio': final_metrics.get('All_Embedded_Clauses_Ratio', 0),
                    'CEFR_NVJD_A1A2_lemma_ratio': final_metrics.get('CEFR_NVJD_A1A2_lemma_ratio', 0)
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
            
            #구문 수정 실패 시   
            except Exception as e:
                step2_time = time.time() - step2_start_time
                step_results.append(StepResult(
                    step_name="구문 수정",
                    status=f"[revise] 구문 수정 실패 - {str(e)}",
                    success=False,
                    processing_time=step2_time,
                    error_message=str(e)
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
                    candidates_generated=0,  # 예외 발생시 기본값
                    candidates_passed=0,      # 예외 발생시 기본값
                    total_processing_time=total_time,
                    error_message=str(e)
                )
            
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
        
        # revision 실패시 
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
    
    async def fix_syntax_batch(self, items: List[SyntaxFixRequest], max_concurrent: int = None) -> List[SyntaxFixResponse]:
        """
        [DEPRECATED] 여러 텍스트를 병렬로 구문 수정합니다.
        
        ⚠️ 이 메서드는 더 이상 사용되지 않습니다.
        대신 text_processing_service_v2.fix_revise_batch를 사용하세요.
        
        Args:
            items: 구문 수정할 텍스트 리스트
            max_concurrent: 최대 동시 처리 개수
            
        Returns:
            구문 수정 결과 리스트 (구문만, 어휘 수정 없음)
        """
        if max_concurrent is None:
            max_concurrent = self.max_concurrent
            
        logger.info(f"배치 구문 수정 시작: {len(items)}개 항목, 최대 동시 처리: {max_concurrent}개")
        
        # 세마포어를 사용한 동시 처리 제한
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_single_item(item: SyntaxFixRequest) -> SyntaxFixResponse:
            async with semaphore:
                return await self.fix_syntax_single(item)
        
        tasks = [process_single_item(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"항목 {i} 구문 수정 실패: {str(result)}")
                processed_results.append(SyntaxFixResponse(
                    request_id=items[i].request_id,
                    overall_success=False,
                    original_text=items[i].text,
                    final_text=None,
                    revision_success=False,
                    step_results=[],
                    original_metrics=None,
                    final_metrics=None,
                    candidates_generated=0,
                    candidates_passed=0,
                    total_processing_time=0.0,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        logger.info(f"배치 구문 수정 완료: {len(processed_results)}개 결과")
        return processed_results


# [DEPRECATED] 전역 텍스트 처리 서비스 인스턴스
# ⚠️ 사용하지 마세요. text_processing_service_v2를 사용하세요.
text_processing_service = TextProcessingService() 