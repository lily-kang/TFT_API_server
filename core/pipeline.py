import asyncio
from typing import Dict, Any, List
from core.analyzer import analyzer
from core.metrics import metrics_extractor
from core.judge import judge
from core.llm.syntax_fixer import syntax_fixer
from core.llm.lexical_fixer import lexical_fixer
from models.request import PipelineItem, ToleranceAbs, ToleranceRatio
from models.response import (
    PipelineResult, StatusEnum, PassEnum, AttemptCounts, TraceStep
)
from config.settings import settings
from utils.exceptions import PipelineError
from utils.logging import logger


class PipelineProcessor:
    """파이프라인 처리 클래스"""
    
    async def run_pipeline(self, payload: PipelineItem) -> PipelineResult:
        """
        단일 지문에 대한 파이프라인을 실행합니다.
        
        Args:
            payload: 파이프라인 처리 항목
            
        Returns:
            처리 결과
        """
        try:
            # 초기 설정
            text = payload.generated_passage or payload.original_text
            master = payload.master
            tolerance_abs = payload.tolerance_abs or ToleranceAbs(**settings.default_tolerance_abs)
            tolerance_ratio = payload.tolerance_ratio or ToleranceRatio(**settings.default_tolerance_ratio)
            
            trace = []
            attempts = AttemptCounts()
            
            logger.info(f"파이프라인 시작: client_id={payload.client_id}")
            
            # 1단계: 초기 분석
            raw_analysis = await analyzer.analyze(text, payload.include_syntax)
            metrics = metrics_extractor.extract(raw_analysis)
            evaluation = judge.evaluate(metrics, master, tolerance_abs, tolerance_ratio)
            
            # 상세 결과 포맷팅
            detailed_result = metrics_extractor.format_detailed_result(metrics, evaluation.detailed_metrics)
            
            trace.append(TraceStep(
                step="analyze",
                metrics=metrics.dict(),
                syntax_pass=evaluation.syntax_pass,
                lexical_pass=evaluation.lexical_pass
            ))
            
            # 모든 지표 통과 시 즉시 반환
            if evaluation.syntax_pass == "PASS" and evaluation.lexical_pass == "PASS":
                return self._create_final_result(
                    payload.client_id, text, evaluation, detailed_result, attempts, trace
                )
            
            # 2단계: 구문 수정 (필요 시)
            if evaluation.syntax_pass != "PASS":
                text, evaluation, detailed_result = await self._fix_syntax_step(
                    text, payload, master, tolerance_abs, tolerance_ratio, attempts, trace
                )
                
                # 구문 수정 후에도 실패하면 discard
                if evaluation.syntax_pass != "PASS":
                    return self._create_discard_result(
                        payload.client_id, "syntax_fail", evaluation, detailed_result, attempts, trace
                    )
                
                # 구문 수정 후 어휘도 통과하면 완료
                if evaluation.lexical_pass == "PASS":
                    return self._create_final_result(
                        payload.client_id, text, evaluation, detailed_result, attempts, trace
                    )
            
            # 3단계: 어휘 수정 (필요 시)
            if evaluation.lexical_pass != "PASS":
                text, evaluation, detailed_result = await self._fix_lexical_step(
                    text, payload, master, tolerance_ratio, attempts, trace
                )
                
                # 어휘 수정 후 모든 지표 확인
                if evaluation.syntax_pass == "PASS" and evaluation.lexical_pass == "PASS":
                    return self._create_final_result(
                        payload.client_id, text, evaluation, detailed_result, attempts, trace
                    )
                else:
                    return self._create_discard_result(
                        payload.client_id, "lexical_fail", evaluation, detailed_result, attempts, trace
                    )
                    
        except Exception as e:
            logger.error(f"파이프라인 실행 실패 (client_id={payload.client_id}): {str(e)}")
            return PipelineResult(
                client_id=payload.client_id,
                status=StatusEnum.ERROR,
                syntax_pass=PassEnum.FAIL,
                lexical_pass=PassEnum.FAIL,
                detailed_result="파이프라인 실행 중 오류 발생",
                final_text=None,
                attempts=AttemptCounts(),
                error_message=str(e)
            )
    
    async def _fix_syntax_step(
        self, text: str, payload: PipelineItem, master, tolerance_abs, tolerance_ratio,
        attempts: AttemptCounts, trace: List[TraceStep]
    ) -> tuple:
        """구문 수정 단계"""
        logger.info(f"구문 수정 시작: client_id={payload.client_id}")
        
        candidates, selected_text = await syntax_fixer.fix_syntax(
            text, master, tolerance_abs, tolerance_ratio, payload.syntax_candidates
        )
        attempts.syntax += 1
        text = selected_text
        
        trace.append(TraceStep(
            step="fix_syntax",
            candidates=candidates,
            selected=selected_text
        ))
        
        # 재분석
        raw_analysis = await analyzer.analyze(text, payload.include_syntax)
        metrics = metrics_extractor.extract(raw_analysis)
        evaluation = judge.evaluate(metrics, master, tolerance_abs, tolerance_ratio)
        detailed_result = metrics_extractor.format_detailed_result(metrics, evaluation.detailed_metrics)
        
        trace.append(TraceStep(
            step="reanalyze_after_syntax",
            metrics=metrics.dict(),
            syntax_pass=evaluation.syntax_pass,
            lexical_pass=evaluation.lexical_pass
        ))
        
        return text, evaluation, detailed_result
    
    async def _fix_lexical_step(
        self, text: str, payload: PipelineItem, master, tolerance_ratio,
        attempts: AttemptCounts, trace: List[TraceStep]
    ) -> tuple:
        """어휘 수정 단계"""
        logger.info(f"어휘 수정 시작: client_id={payload.client_id}")
        
        candidates, selected_text = await lexical_fixer.fix_lexical(
            text, master, tolerance_ratio, payload.lexical_candidates
        )
        attempts.lexical += 1
        text = selected_text
        
        trace.append(TraceStep(
            step="fix_lexical",
            candidates=candidates,
            selected=selected_text
        ))
        
        # 재분석 (구문과 어휘 모두 확인)
        raw_analysis = await analyzer.analyze(text, payload.include_syntax)
        metrics = metrics_extractor.extract(raw_analysis)
        evaluation = judge.evaluate(metrics, master, payload.tolerance_abs, tolerance_ratio)
        detailed_result = metrics_extractor.format_detailed_result(metrics, evaluation.detailed_metrics)
        
        trace.append(TraceStep(
            step="reanalyze_after_lexical",
            metrics=metrics.dict(),
            syntax_pass=evaluation.syntax_pass,
            lexical_pass=evaluation.lexical_pass
        ))
        
        return text, evaluation, detailed_result
    
    def _create_final_result(
        self, client_id: str, text: str, evaluation, detailed_result: str,
        attempts: AttemptCounts, trace: List[TraceStep]
    ) -> PipelineResult:
        """최종 성공 결과 생성"""
        return PipelineResult(
            client_id=client_id,
            status=StatusEnum.FINAL,
            syntax_pass=PassEnum.PASS,
            lexical_pass=PassEnum.PASS,
            detailed_result=detailed_result,
            final_text=text,
            attempts=attempts,
            trace=trace
        )
    
    def _create_discard_result(
        self, client_id: str, reason: str, evaluation, detailed_result: str,
        attempts: AttemptCounts, trace: List[TraceStep]
    ) -> PipelineResult:
        """폐기 결과 생성"""
        status_map = {
            "syntax_fail": StatusEnum.SYNTAX_FAIL,
            "lexical_fail": StatusEnum.LEXICAL_FAIL
        }
        
        return PipelineResult(
            client_id=client_id,
            status=status_map.get(reason, StatusEnum.ERROR),
            syntax_pass=PassEnum(evaluation.syntax_pass),
            lexical_pass=PassEnum(evaluation.lexical_pass),
            detailed_result=detailed_result,
            final_text=None,
            attempts=attempts,
            trace=trace
        )


class BatchProcessor:
    """배치 처리 클래스"""
    
    def __init__(self):
        self.pipeline_processor = PipelineProcessor()
    
    async def process_batch(self, items: List[PipelineItem]) -> List[PipelineResult]:
        """
        여러 지문을 병렬로 처리합니다.
        
        Args:
            items: 처리할 지문 리스트
            
        Returns:
            처리 결과 리스트
        """
        logger.info(f"배치 처리 시작: {len(items)}개 항목")
        
        # 병렬 처리
        tasks = [
            self.pipeline_processor.run_pipeline(item)
            for item in items
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"항목 {i} 처리 실패: {str(result)}")
                processed_results.append(PipelineResult(
                    client_id=items[i].client_id,
                    status=StatusEnum.ERROR,
                    syntax_pass=PassEnum.FAIL,
                    lexical_pass=PassEnum.FAIL,
                    detailed_result="처리 중 예외 발생",
                    final_text=None,
                    attempts=AttemptCounts(),
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        logger.info(f"배치 처리 완료: {len(processed_results)}개 결과")
        return processed_results


# 전역 배치 처리기 인스턴스
batch_processor = BatchProcessor() 