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
    """텍스트 처리 서비스 (구문/어휘 수정)"""
    
    def __init__(self):
        self.max_concurrent = 10  # 기본 배치 동시 처리 개수
    
    async def fix_syntax_single(self, request: SyntaxFixRequest) -> SyntaxFixResponse:
        """
        단일 텍스트 구문 수정 (기존 API 로직 그대로)
        
        Args:
            request: 구문 수정 요청
            
        Returns:
            구문 수정 결과
        """
        total_start_time = time.time()
        step_results = []
        
        try:
            logger.info(f"구문 수정 시작: request_id={request.request_id}, 텍스트={len(request.text)}글자")
            
            # settings에서 기본 허용 오차 사용
            tolerance_abs = ToleranceAbs()  # 기본값 사용
            tolerance_ratio = ToleranceRatio()  # 기본값 사용
            referential_clauses = request.referential_clauses or ""
            
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
                
                step1_time = time.time() - step1_start_time
                step_results.append(StepResult(
                    step_name="원본 분석",
                    success=True,
                    processing_time=step1_time,
                    details={
                        "syntax_pass": original_evaluation.syntax_pass
                    }
                ))
                
                logger.info(f"[{request.request_id}] 1단계 완료 - 구문 통과?: {original_evaluation.syntax_pass}")
                
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
                # 구문 패스하면 일단 어휘 수정
                # 3단계: 어휘 수정 
                step_results.append(StepResult(
                    step_name="어휘 수정(지금은 안함)",
                    success=False,
                    processing_time=0.0,
                    error_message="구문이 이미 통과하여 어휘 수정 단계로"
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
            
            # 2단계: 실패시 구문 수정 수행
            step2_start_time = time.time()
            logger.info(f"[{request.request_id}] 2단계: 구문 수정 시작")
            
            try:
                # 기존 fix_syntax 인터페이스를 새로운 요청 파라미터에 맞게 수정
                current_metrics_dict = {
                    'AVG_SENTENCE_LENGTH': original_metrics.AVG_SENTENCE_LENGTH,
                    'All_Embedded_Clauses_Ratio': original_metrics.All_Embedded_Clauses_Ratio,
                    'CEFR_NVJD_A1A2_lemma_ratio': original_metrics.CEFR_NVJD_A1A2_lemma_ratio
                }
                
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
                
                # if problematic_metric is None:
                #     # 문제가 있는 지표가 없으면 구문 수정 불필요
                #     step_results.append(StepResult(
                #         step_name="어휘 수정",
                #         success=False,
                #         processing_time=0.0,
                #         error_message="구문이 이미 통과하여 어휘 수정 단계 스킵"
                #     ))
                    
                #     total_time = time.time() - total_start_time
                #     logger.info(f"[{request.request_id}] 구문 수정 불필요 (이미 통과)")
                    
                #     return SyntaxFixResponse(
                #         request_id=request.request_id,
                #         overall_success=True,
                #         original_text=request.text,
                #         final_text=request.text,  # 원본과 동일
                #         revision_success=True,
                #         step_results=step_results,
                #         original_metrics=original_metrics_dict,
                #         final_metrics=original_metrics_dict,
                #         candidates_generated=0,
                #         candidates_passed=1,
                #         total_processing_time=total_time
                #     )
                
                # 수정 문장 수 자동 계산
                # 목표 범위 계산
                if problematic_metric == "avg_sentence_length":
                    target_min = request.master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                    target_max = request.master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
                    current_value = original_metrics.AVG_SENTENCE_LENGTH
                else:
                    clause_tolerance = request.master.All_Embedded_Clauses_Ratio * tolerance_ratio.All_Embedded_Clauses_Ratio
                    target_min = request.master.All_Embedded_Clauses_Ratio - clause_tolerance
                    target_max = request.master.All_Embedded_Clauses_Ratio + clause_tolerance
                    current_value = original_metrics.All_Embedded_Clauses_Ratio
                
                # 분석 결과에서 필요한 정보 추출 (metrics.py와 동일한 구조 사용)
                data = original_analysis.get("data", {})
                text_statistics = data.get("text_statistics", {})
                
                basic_overview = text_statistics.get("table_01_basic_overview", {})
                syntax_analysis = text_statistics.get("table_10_syntax_analysis", {})
                table_02 = text_statistics.get("table_02_detailed_tokens", {})
                table_09 = text_statistics.get("table_09_pos_distribution", {})
                table_11 = text_statistics.get("table_11_lemma_metrics", {})
                table_12 = text_statistics.get("table_12_unique_lemma_list", {})
                
                sentence_count = basic_overview.get('sentence_count', 0)
                avg_sentence_length = basic_overview.get('avg_sentence_length', 0.0)
                lexical_tokens = table_02.get('lexical_tokens', 0)  # t2 테이블에서 가져오기
                
                # 구문 수정용 분석 결과
                analysis_result = {
                    'sentence_count': sentence_count,
                    'lexical_tokens': lexical_tokens,
                    'adverbial_clause_sentences': syntax_analysis.get('adverbial_clause_sentences', 0),
                    'coordinate_clause_sentences': syntax_analysis.get('coordinate_clause_sentences', 0),
                    'nominal_clause_sentences': syntax_analysis.get('nominal_clause_sentences', 0),
                    'relative_clause_sentences': syntax_analysis.get('relative_clause_sentences', 0)
                }
                
                # # 어휘 수정용 분석 결과
                # lexical_analysis_result = {
                #     'content_lemmas': table_02.get('content_lemmas', 0),
                #     'propn_lemma_count': table_09.get('propn_lemma_count', 0),
                #     'cefr_a1_NVJD_lemma_count': table_11.get('cefr_a1_NVJD_lemma_count', 0),
                #     'cefr_a2_NVJD_lemma_count': table_11.get('cefr_a2_NVJD_lemma_count', 0)
                # }
                
                # # CEFR breakdown 추출 (table_12에서) - 객체 형태로
                # cefr_breakdown = table_12.get('cefr_breakdown', {})
                
                logger.info(f"[{request.request_id}] 수정 문장 수 계산 시작")
                logger.info(f"[{request.request_id}] problematic_metric: {problematic_metric}")
                logger.info(f"[{request.request_id}] current_value: {current_value:.3f}")
                logger.info(f"[{request.request_id}] target_min: {target_min:.3f}, target_max: {target_max:.3f}")
                logger.info(f"[{request.request_id}] analysis_result: {analysis_result}")
                
                modification_params = prompt_builder.calculate_modification_count(
                    problematic_metric, current_value, target_min, target_max, analysis_result
                )
                
                num_modifications = modification_params['num_modifications']
                # 기존 서비스는 prompt_type을 사용하지 않으므로 무시
                
                logger.info(f"[{request.request_id}] 계산된 수정 문장 수: {num_modifications}")
                
                # fix_syntax_with_params 호출 (계산된 값 전달)
                candidates, selected_text, final_metrics, final_evaluation, total_candidates_generated = await syntax_fixer.fix_syntax_with_params(
                    text=request.text,
                    master=request.master,
                    tolerance_abs=tolerance_abs,
                    tolerance_ratio=tolerance_ratio,
                    current_metrics=current_metrics_dict,
                    num_modifications=num_modifications,
                    problematic_metric=problematic_metric,
                    referential_clauses=referential_clauses
                    # prompt_type은 기본값 "increase" 사용
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
                
                # 3단계: 어휘 수정 (지금은 스킵)
                step_results.append(StepResult(
                    step_name="어휘 수정",
                    success=False,
                    processing_time=0.0,
                    error_message="어휘 수정 단계 스킵"
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
    
    async def fix_syntax_batch(self, items: List[SyntaxFixRequest], max_concurrent: int = None) -> List[SyntaxFixResponse]:
        """
        여러 텍스트를 병렬로 구문 수정합니다.
        
        Args:
            items: 구문 수정할 텍스트 리스트
            max_concurrent: 최대 동시 처리 개수
            
        Returns:
            구문 수정 결과 리스트
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


# 전역 텍스트 처리 서비스 인스턴스
text_processing_service = TextProcessingService() 