import time
import asyncio
from typing import List, Dict, Any
from models.request import SyntaxFixRequest, ToleranceAbs, ToleranceRatio
from models.response import SyntaxFixResponse, StepResult
from core.analyzer import analyzer
from core.metrics import metrics_extractor
from core.judge import judge
from core.llm.syntax_fixer import syntax_fixer
from core.llm.lexical_fixer import lexical_fixer
from core.llm.prompt_builder import prompt_builder
from utils.logging import logger
# import nltk
# nltk.download('punkt')

class TextProcessingService:
    """텍스트 처리 서비스 (구문/어휘 수정)"""
    
    def __init__(self):
        self.max_concurrent = 10  # 기본 배치 동시 처리 개수
    
    async def fix_revise_single(self, request: SyntaxFixRequest) -> SyntaxFixResponse:
        """
        결합 리비전: 구문 수정 → 구문 결과 분석 → 어휘 통과 여부 확인 → 필요 시 어휘 단계로 분기
        """
        total_start_time = time.time()
        step_results = []
        try:
            logger.info(f"[revise] Start: request_id={request.request_id}, Text={len(request.text)}글자")

            # 기본 허용오차 로딩
            tolerance_abs = ToleranceAbs()
            tolerance_ratio = ToleranceRatio()
            referential_clauses = request.referential_clauses or ""

            # 1) 텍스트 분석
            analysis_start_time = time.time()
            try:
                original_analysis = await analyzer.analyze(request.text, include_syntax=True)
                original_metrics = metrics_extractor.extract(original_analysis)
                original_evaluation = judge.evaluate(original_metrics, request.master, tolerance_abs, tolerance_ratio)

                original_metrics_dict = {
                    'AVG_SENTENCE_LENGTH': original_metrics.get('AVG_SENTENCE_LENGTH', 0),
                    'All_Embedded_Clauses_Ratio': original_metrics.get('All_Embedded_Clauses_Ratio', 0),
                    'CEFR_NVJD_A1A2_lemma_ratio': original_metrics.get('CEFR_NVJD_A1A2_lemma_ratio', 0)
                }

                step_results.append(StepResult(
                    step_name="원본 지문 분석",
                    success=True,
                    status=f"[revise] 원본 분석 완료 - 구문: {original_evaluation.syntax_pass}, 어휘: {original_evaluation.lexical_pass}",
                    processing_time=time.time() - analysis_start_time,
                    details={
                        "syntax_pass": original_evaluation.syntax_pass,
                        "lexical_pass": original_evaluation.lexical_pass,
                        "details": original_evaluation.details
                    }
                ))
                
                logger.info(f"[revise] 원본 분석 완료 - 구문: {original_evaluation.syntax_pass}, 어휘: {original_evaluation.lexical_pass}")
            except Exception as e:
                step_results.append(StepResult(
                    step_name="원본 지문 분석",
                    status=f"[revise] 원본 분석 실패 - {str(e)}",
                    success=False,
                    processing_time=time.time() - analysis_start_time,
                    error_message=str(e)
                ))
                raise

            # 2) 구문 PASS & 어휘 PASS → 즉시 종료
            if original_evaluation.syntax_pass == "PASS" and original_evaluation.lexical_pass == "PASS":
                total_time = time.time() - total_start_time
                logger.info(f"[revise] 구문 & 어휘 모두 통과 → 즉시 종료")
                step_results.append(StepResult(
                    step_name="구문 수정",
                    status=f"[revise] 구문 & 어휘 모두 통과",
                    success=True,
                    processing_time=0.0,
                    details={
                        "skipped": True,
                        "reason": "구문 통과로 스킵",
                        "candidates_generated": 0,
                        "candidates_passed": 0
                    }
                ))
                step_results.append(StepResult(
                    step_name="어휘 수정",
                    status=f"[revise] 구문 & 어휘 모두 통과",
                    success=True,
                    processing_time=0.0,
                    details={
                        "skipped": True,
                        "reason": "구문 통과로 스킵",
                        "candidates_generated": 0,
                        "candidates_passed": 0
                    }
                ))
                
                return SyntaxFixResponse(
                    request_id=request.request_id,
                    overall_success=True,
                    original_text=request.text,
                    final_text=request.text,
                    revision_success=True,
                    step_results=step_results,
                    original_metrics=original_metrics_dict,
                    final_metrics=original_metrics_dict,
                    candidates_generated=0,
                    candidates_passed=0,
                    total_processing_time=total_time
                )
            
            # 3) 구문 PASS & 어휘 FAIL → 바로 어휘 수정으로 분기
            if original_evaluation.syntax_pass == "PASS" and original_evaluation.lexical_pass == "FAIL":
                logger.info("=" * 80)
                logger.info("⚡ [REVISE] 구문 통과 & 어휘 실패 → 바로 어휘 수정으로 분기")
                logger.info("=" * 80)
                logger.info(f"📊 원본 지표:")
                logger.info(f"   - 평균 문장 길이: {original_metrics.AVG_SENTENCE_LENGTH:.3f} ✅ PASS")
                logger.info(f"   - 내포절 비율: {original_metrics.All_Embedded_Clauses_Ratio:.3f} ✅ PASS")
                logger.info(f"   - CEFR A1A2 비율: {original_metrics.CEFR_NVJD_A1A2_lemma_ratio:.4f} ❌ FAIL")
                logger.info("=" * 80)
                
                selected_text = request.text
                candidates_generated = 0
                candidates_passed = 0
                
                # 어휘 수정 단계로 직접 이동 (구문 수정 단계 스킵)
                step_results.append(StepResult(
                    step_name="구문 수정",
                    status=f"[revise] syntax PASS & vocab FAIL → 어휘 수정 모듈",
                    success=True,
                    processing_time=0.0,
                    details={
                        "skipped": True,
                        "reason": "구문 통과로 스킵",
                        "candidates_generated": 0,
                        "candidates_passed": 0
                    }
                ))
                
                
                # 바로 어휘 수정 단계로 분기
                selected_candidate_lexical_pass = "FAIL"  # 원본이 어휘 실패했으므로
                
            # 4) 구문 FAIL → 구문 수정 수행
            elif original_evaluation.syntax_pass == "FAIL":
                logger.info("=" * 80)
                logger.info("🔧 [REVISE] 구문 수정 단계 시작")
                logger.info("=" * 80)
                logger.info(f"📊 원본 지표:")
                logger.info(f"   - 평균 문장 길이: {original_metrics.AVG_SENTENCE_LENGTH:.3f}")
                logger.info(f"   - 내포절 비율: {original_metrics.All_Embedded_Clauses_Ratio:.3f}")
                logger.info(f"   - CEFR A1A2 비율: {original_metrics.CEFR_NVJD_A1A2_lemma_ratio:.4f}")
                logger.info("=" * 80)
                
                selected_text = request.text
                candidates_generated = 0
                candidates_passed = 0
                syntax_candidates_lexical = []
                selected_candidate_lexical_pass = None

                # 구문 수정 시작 시간 측정
                syntax_fix_start_time = time.time()
                try:
                    # 문제 지표 계산
                    problematic_metric = prompt_builder.determine_problematic_metric(
                        {
                            'avg_sentence_length': original_metrics.AVG_SENTENCE_LENGTH,
                            'embedded_clauses_ratio': original_metrics.All_Embedded_Clauses_Ratio
                        },
                        request.master, tolerance_abs, tolerance_ratio
                    )

                    # 목표 범위 계산
                    if problematic_metric == "avg_sentence_length":
                        target_min = request.master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                        target_max = request.master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
                        current_value = original_metrics.AVG_SENTENCE_LENGTH
                    else:
                        target_min = request.master.All_Embedded_Clauses_Ratio - tolerance_ratio.All_Embedded_Clauses_Ratio
                        target_max = request.master.All_Embedded_Clauses_Ratio + tolerance_ratio.All_Embedded_Clauses_Ratio
                        current_value = original_metrics.All_Embedded_Clauses_Ratio

                    analysis_result = {
                        'sentence_count': original_metrics.sentence_count,
                        'lexical_tokens': original_metrics.lexical_tokens,
                        'total_clause_sentences': original_metrics.total_clause_sentences
                    }

                    modification_params = prompt_builder.calculate_modification_count(
                        problematic_metric, current_value, target_min, target_max, analysis_result
                    )
                    num_modifications = modification_params['num_modifications']
                    prompt_type = modification_params['prompt_type']

                    avg_target_min = request.master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                    avg_target_max = request.master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
                    clause_target_min = request.master.All_Embedded_Clauses_Ratio - tolerance_ratio.All_Embedded_Clauses_Ratio
                    clause_target_max = request.master.All_Embedded_Clauses_Ratio + tolerance_ratio.All_Embedded_Clauses_Ratio

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
                    candidates_generated = total_candidates_generated
                    candidates_passed = len(candidates)

                    # 최종 선택된 후보의 어휘 통과 여부는 final_metrics에서 직접 계산하여 재분석을 피함
                    lex_target_min = request.master.CEFR_NVJD_A1A2_lemma_ratio - tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio
                    lex_target_max = request.master.CEFR_NVJD_A1A2_lemma_ratio + tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio
                    lex_current = final_metrics.CEFR_NVJD_A1A2_lemma_ratio
                    selected_candidate_lexical_pass = "PASS" if lex_target_min <= lex_current <= lex_target_max else "FAIL"

                    logger.info("=" * 80)
                    logger.info("✅ [REVISE] 구문 수정 완료")
                    logger.info("=" * 80)
                    logger.info(f"📊 최종 구문 지표:")
                    logger.info(f"   - 평균 문장 길이: {final_metrics.AVG_SENTENCE_LENGTH:.3f}")
                    logger.info(f"   - 내포절 비율: {final_metrics.All_Embedded_Clauses_Ratio:.3f}")
                    logger.info(f"📊 어휘 평가:")
                    logger.info(f"   - CEFR A1A2 비율: {lex_current:.4f}")
                    logger.info(f"   - 목표 범위: [{lex_target_min:.4f} ~ {lex_target_max:.4f}]")
                    logger.info(f"   - 어휘 통과 여부: {selected_candidate_lexical_pass}")
                    logger.info("=" * 80)

                    step_results.append(StepResult(
                        step_name="구문 수정",
                        status=f"[revise] syntax revision success & vocab {selected_candidate_lexical_pass}",
                        success=True,
                        processing_time=time.time() - syntax_fix_start_time,
                        details={
                            "skipped": False,
                            "candidates_generated": candidates_generated,
                            "candidates_passed": candidates_passed,
                            "selected_candidate_lexical": {
                                "lexical_pass": selected_candidate_lexical_pass,
                                "cefr_a1a2_ratio": lex_current,
                                "target_min": lex_target_min,
                                "target_max": lex_target_max
                            }
                        }
                    ))
                    
                    # 어휘 수정 단계 기록 (어휘 PASS로 별도 수정 불필요)
                    # step_results.append(StepResult(
                    #     step_name="어휘 수정",
                    #     status="[revise] lexical check PASS (no lexical fixing needed)",
                    #     success=True,
                    #     processing_time=0.0,
                    #     details={
                    #         "skipped": True,
                    #         "reason": "구문 수정된 지문이 어휘 지표도 통과하여 어휘 수정 불필요",
                    #         "lexical_pass": selected_candidate_lexical_pass,
                    #         "cefr_a1a2_ratio": lex_current,
                    #         "target_min": lex_target_min,
                    #         "target_max": lex_target_max
                    #     }
                    # ))

                except Exception as e:
                    step_results.append(StepResult(
                        step_name="구문 수정",
                        status=f"[revise] syntax revision FAIL - {str(e)}",
                        success=False,
                        processing_time=time.time() - syntax_fix_start_time,
                        error_message=str(e)
                    ))
                    # 구문 수정 실패 시 조기 반환
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
                        candidates_generated=candidates_generated,
                        candidates_passed=candidates_passed,
                        total_processing_time=total_time,
                        error_message=str(e)
                    )
            else:
                # 구문 PASS & 어휘 PASS인 경우는 이미 위에서 처리됨
                logger.error("[revise] 예상치 못한 분기")
                raise Exception("예상치 못한 평가 결과 조합")

            # 5) 선택된 텍스트의 최종 지표 준비 (재분석 없이 기존 결과 활용)
            if original_evaluation.syntax_pass == "PASS":
                # 구문이 원래 통과했으면 원본 지표 사용
                final_metrics_dict = original_metrics_dict.copy()
            else:
                # 구문 수정을 거쳤으면 구문 수정 결과의 지표 사용
                final_metrics_dict = {
                    'AVG_SENTENCE_LENGTH': final_metrics.AVG_SENTENCE_LENGTH,
                    'All_Embedded_Clauses_Ratio': final_metrics.All_Embedded_Clauses_Ratio,
                    'CEFR_NVJD_A1A2_lemma_ratio': final_metrics.CEFR_NVJD_A1A2_lemma_ratio
                }

            # 6) 어휘 통과 여부에 따른 분기
            if selected_candidate_lexical_pass == "PASS":
                # 어휘 통과 → 최종 종료
                total_time = time.time() - total_start_time
                logger.info(f"[revise] 선택된 텍스트 어휘 통과 → 최종 종료")
                return SyntaxFixResponse(
                    request_id=request.request_id,
                    overall_success=True,
                    original_text=request.text,
                    final_text=selected_text,
                    revision_success=True,
                    step_results=step_results,
                    original_metrics=original_metrics_dict,
                    final_metrics=final_metrics_dict,
                    candidates_generated=candidates_generated,
                    candidates_passed=candidates_passed,
                    total_processing_time=total_time
                )

            # 7) 어휘 수정 단계 (lexical_fixer 연동)
            logger.info("=" * 80)
            logger.info("📚 [REVISE] 어휘 수정 단계 시작")
            logger.info("=" * 80)
            
            t3=time.time()
            try:
                # 분기별 텍스트 및 지표 소스 결정
                if original_evaluation.syntax_pass == "PASS":
                    # 원본 구문 PASS → 원본 텍스트 기준
                    text_for_lex = request.text
                    src_metrics = original_metrics
                    logger.info("📝 원본 텍스트 기준 (구문 수정 없음)")
                else:
                    # 구문 수정 후 후보 선택 → 선택 텍스트 기준
                    text_for_lex = selected_text
                    # final_metrics에는 NVJD 카운트가 포함됨 (metrics_extractor 확장)
                    src_metrics = final_metrics
                    logger.info("📝 구문 수정된 텍스트 기준")

                # NVJD 카운트 및 현재 비율 산출
                nvjd_total = max(1, int(src_metrics.content_lemmas or 0) - int(src_metrics.propn_lemma_count or 0))
                nvjd_a1a2 = int(src_metrics.cefr_a1_NVJD_lemma_count or 0) + int(src_metrics.cefr_a2_NVJD_lemma_count or 0)
                current_ratio = float(src_metrics.CEFR_NVJD_A1A2_lemma_ratio)

                logger.info(f"📊 현재 어휘 지표:")
                logger.info(f"   - NVJD 총 렘마: {nvjd_total}")
                logger.info(f"   - NVJD A1A2 렘마: {nvjd_a1a2}")
                logger.info(f"   - 현재 CEFR A1A2 비율: {current_ratio:.4f}")

                # 수정 단어 수 계산 (프롬프트 빌더)
                lex_calc = prompt_builder.calculate_lexical_modification_count_nvjd(
                    current_ratio=current_ratio,
                    nvjd_total_lemma_count=nvjd_total,
                    nvjd_a1a2_lemma_count=nvjd_a1a2,
                    master=request.master,
                    tolerance_ratio=tolerance_ratio
                )
                lex_num_mods = int(lex_calc.get('num_modifications', 0))
                lex_direction = lex_calc.get('direction', 'increase')
                
                logger.info(f"🎯 어휘 수정 계획:")
                logger.info(f"   - 수정 방향: {lex_direction}")
                logger.info(f"   - 수정 단어 수: {lex_num_mods}")
                logger.info(f"   - 목표 범위: {lex_calc.get('target_lower', 0):.4f} ~ {lex_calc.get('target_upper', 0):.4f}")
                logger.info("=" * 80)

                # 어휘 후보 생성 및 취합 (0인 경우도 프롬프트 최소 1개 수행할지 정책에 따라 조정 가능)
                normalized_text_for_lex = " ".join(text_for_lex.split())
                lex_mods, lex_selected_text, lex_metrics, _lex_eval, lex_candidates_generated = await lexical_fixer.fix_lexical_with_params(
                    text=normalized_text_for_lex,
                    master=request.master,
                    tolerance_ratio=tolerance_ratio,
                    current_cefr_ratio=current_ratio,
                    direction=lex_direction,
                    nvjd_total_lemma_count=nvjd_total,
                    nvjd_a1a2_lemma_count=nvjd_a1a2,
                    cefr_breakdown=src_metrics.cefr_breakdown
                )

                logger.info("=" * 80)
                logger.info("✅ [REVISE] 어휘 수정 완료")
                logger.info("=" * 80)
                logger.info(f"📊 어휘 후보 생성: {lex_candidates_generated}개")
                logger.info(f"📋 최종 어휘 지표:")
                logger.info(f"   - CEFR A1A2 비율: {lex_metrics.get('CEFR_NVJD_A1A2_lemma_ratio', 0):.4f}")
                logger.info(f"   - NVJD 총 렘마: {lex_metrics.get('NVJD_total_lemma_count', 0)}")
                logger.info(f"   - NVJD A1A2 렘마: {lex_metrics.get('NVJD_A1A2_lemma_count', 0)}")
                logger.info("=" * 80)
                
                step_results.append(StepResult(
                    step_name="어휘 수정",
                    status=f"[revise] vocab revision success",
                    success=True,
                    processing_time=time.time() - t3,
                    details={
                        "current_ratio": current_ratio,
                        "nvjd_total_lemma_count": nvjd_total,
                        "nvjd_a1a2_lemma_count": nvjd_a1a2,
                        "num_modifications": lex_num_mods,
                        "direction": lex_direction,
                        "lexical_candidates_generated": lex_candidates_generated,
                        "lexical_candidates": lex_metrics.get('lexical_candidates'),
                        "lexical_sheet_data_merged": lex_metrics.get('lexical_sheet_data_merged')
                    }
                ))

                total_time = time.time() - total_start_time
                return SyntaxFixResponse(
                    request_id=request.request_id,
                    overall_success=True,
                    original_text=request.text,
                    final_text=selected_text,
                    revision_success=True,
                    step_results=step_results,
                    original_metrics=original_metrics_dict,
                    final_metrics=final_metrics_dict,
                    candidates_generated=candidates_generated,
                    candidates_passed=candidates_passed,
                    total_processing_time=total_time,
                    error_message=str(e)
                )
            except Exception as e:
                step_results.append(StepResult(
                    step_name="어휘 수정",
                    status=f"[revise] vocab revision FAIL - {str(e)}",
                    success=False,
                    processing_time=time.time() - t3,
                    error_message=str(e)
                ))

                total_time = time.time() - total_start_time
                return SyntaxFixResponse(
                    request_id=request.request_id,
                    overall_success=True,
                    original_text=request.text,
                    final_text=selected_text,
                    revision_success=False,
                    step_results=step_results,
                    original_metrics=original_metrics_dict,
                    final_metrics=final_metrics_dict,
                    candidates_generated=candidates_generated,
                    candidates_passed=candidates_passed,
                    total_processing_time=total_time,
                    error_message=str(e)
                )
        except Exception as e:
            total_time = time.time() - total_start_time
            logger.error(f"[revise] 전체 실행 실패: {str(e)}")
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
                error_message=str(e)
            )

    async def fix_revise_batch(self, items: List[SyntaxFixRequest], max_concurrent: int = None) -> List[SyntaxFixResponse]:
        """
        결합 리비전 배치 처리
        """
        if max_concurrent is None:
            max_concurrent = self.max_concurrent

        logger.info(f"[revise] 배치 시작: {len(items)}개, 동시 처리={max_concurrent}")
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_item(item: SyntaxFixRequest) -> SyntaxFixResponse:
            async with semaphore:
                return await self.fix_revise_single(item)

        tasks = [process_item(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed: List[SyntaxFixResponse] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"[revise] 항목 {i} 실패: {str(r)}")
                processed.append(SyntaxFixResponse(
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
                    error_message=str(r)
                ))
            else:
                processed.append(r)
        logger.info(f"[revise] 배치 완료: {len(processed)}개 결과")
        return processed

# 전역 텍스트 처리 서비스 인스턴스
text_processing_service = TextProcessingService() 