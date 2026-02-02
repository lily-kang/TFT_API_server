from typing import Dict, Any
from models.internal import MetricsData, EvaluationResult, ToleranceRange
from models.request import MasterMetrics, ToleranceAbs, ToleranceRatio
from config.settings import settings
from utils.exceptions import EvaluationError
from utils.logging import logger


class MetricsJudge:
    """지표 평가 및 Pass/Fail 판단 클래스"""
    
    def evaluate(
        self,
        metrics: MetricsData,
        master: MasterMetrics,
        tolerance_abs: ToleranceAbs = None,
        tolerance_ratio: ToleranceRatio = None
    ) -> EvaluationResult:
        """
        추출된 지표를 마스터 기준과 비교하여 Pass/Fail을 판단합니다.
        
        Args:
            metrics: 추출된 지표 데이터
            master: 마스터 기준 지표
            tolerance_abs: 절대값 허용 오차
            tolerance_ratio: 비율 허용 오차
            
        Returns:
            평가 결과
            
        Raises:
            EvaluationError: 평가 중 오류 발생 시
        """
        try:
            # 기본값 설정
            if tolerance_abs is None:
                tolerance_abs = ToleranceAbs(**settings.default_tolerance_abs)
            if tolerance_ratio is None:
                tolerance_ratio = ToleranceRatio(**settings.default_tolerance_ratio)
            
            detailed_metrics = {}
            
            # 1. AVG_SENTENCE_LENGTH 평가 (절대값 기준)
            length_range = self._calculate_abs_range(
                master.AVG_SENTENCE_LENGTH,
                tolerance_abs.AVG_SENTENCE_LENGTH
            )
            length_pass = length_range.is_within_range(metrics.AVG_SENTENCE_LENGTH)
            detailed_metrics["AVG_SENTENCE_LENGTH"] = {
                "min_value": round(length_range.min_value, 3),
                "max_value": round(length_range.max_value, 3),
                "current_value": metrics.AVG_SENTENCE_LENGTH,
                "is_pass": length_pass
            }
            
            # 2. All_Embedded_Clauses_Ratio 평가 (비율 기준)
            clause_range = self._calculate_ratio_range(
                master.All_Embedded_Clauses_Ratio,
                tolerance_ratio.All_Embedded_Clauses_Ratio
            )
            clause_pass = clause_range.is_within_range(metrics.All_Embedded_Clauses_Ratio)
            detailed_metrics["All_Embedded_Clauses_Ratio"] = {
                "min_value": round(clause_range.min_value, 3),
                "max_value": round(clause_range.max_value, 3),
                "current_value": metrics.All_Embedded_Clauses_Ratio,
                "is_pass": clause_pass
            }
            
            ## 어휘 지표 평가
            # 3. CEFR_NVJD_A1A2_lemma_ratio 평가 (비율 기준)
            lexical_range = self._calculate_ratio_range(
                master.CEFR_NVJD_A1A2_lemma_ratio,
                tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio
            )
            lexical_pass = lexical_range.is_within_range(metrics.CEFR_NVJD_A1A2_lemma_ratio)
            detailed_metrics["CEFR_NVJD_A1A2_lemma_ratio"] = {
                "min_value": lexical_range.min_value,
                "max_value": lexical_range.max_value,
                "current_value": metrics.CEFR_NVJD_A1A2_lemma_ratio,
                "is_pass": lexical_pass
            }
            
            # 전체 평가 결과
            syntax_pass = "PASS" if (length_pass and clause_pass) else "FAIL"
            lexical_pass = "PASS" if lexical_pass else "FAIL"
            
            result = EvaluationResult(
                syntax_pass=syntax_pass,
                lexical_pass=lexical_pass,
                details=detailed_metrics
            )
            
            logger.info(f"지표 평가 완료: 구문={syntax_pass}, 어휘={lexical_pass}")
            return result
            
        except Exception as e:
            logger.error(f"지표 평가 실패: {str(e)}")
            raise EvaluationError(f"지표 평가 중 오류 발생: {str(e)}")
    
    def _calculate_abs_range(self, master_value: float, tolerance: float) -> ToleranceRange:
        """절대값 기준 허용 범위 계산"""
        return ToleranceRange(
            min_value=master_value - tolerance,
            max_value=master_value + tolerance
        )
    
    def _calculate_ratio_range(self, master_value: float, tolerance_ratio: float) -> ToleranceRange:
        """비율 기준 허용 범위 계산"""
        # tolerance_abs = master_value * tolerance_ratio
        return ToleranceRange(
            min_value=master_value - tolerance_ratio,
            max_value=master_value + tolerance_ratio
        )
    
    def evaluate_with_ranges(
        self,
        metrics: Dict[str, float],
        avg_target_min: float,
        avg_target_max: float,
        clause_target_min: float,
        clause_target_max: float
    ) -> EvaluationResult:
        """
        개별 target 범위로 구문 지표를 평가합니다.
        
        Args:
            metrics: 추출된 지표 데이터 (Dict 형태)
            avg_target_min: 평균 문장 길이 목표 최소값
            avg_target_max: 평균 문장 길이 목표 최대값
            clause_target_min: 내포절 비율 목표 최소값
            clause_target_max: 내포절 비율 목표 최대값
            
        Returns:
            평가 결과
            
        Raises:
            EvaluationError: 평가 중 오류 발생 시
        """
        try:
            detailed_metrics = {}
            
            # 1. AVG_SENTENCE_LENGTH 평가
            avg_length = metrics.get('AVG_SENTENCE_LENGTH', 0)
            length_pass = avg_target_min <= avg_length <= avg_target_max
            detailed_metrics["AVG_SENTENCE_LENGTH"] = {
                "min_value": avg_target_min,
                "max_value": avg_target_max,
                "current_value": avg_length,
                "is_pass": length_pass
            }
            
            # 2. All_Embedded_Clauses_Ratio 평가
            clause_ratio = metrics.get('All_Embedded_Clauses_Ratio', 0)
            clause_pass = clause_target_min <= clause_ratio <= clause_target_max
            detailed_metrics["All_Embedded_Clauses_Ratio"] = {
                "min_value": clause_target_min,
                "max_value": clause_target_max,
                "current_value": clause_ratio,
                "is_pass": clause_pass
            }
            
            # 전체 평가 결과
            syntax_pass = "PASS" if (length_pass and clause_pass) else "FAIL"
            lexical_pass = "PASS"  # 구문 평가에서는 어휘는 항상 PASS로 설정
            
            result = EvaluationResult(
                syntax_pass=syntax_pass,
                lexical_pass=lexical_pass,
                details=detailed_metrics
            )
            
            logger.info(f"개별 범위 지표 평가 완료: 구문={syntax_pass} (길이={length_pass}, 절={clause_pass})")
            return result
            
        except Exception as e:
            logger.error(f"개별 범위 지표 평가 실패: {str(e)}")
            raise EvaluationError(f"개별 범위 지표 평가 중 오류 발생: {str(e)}")


# 전역 판단기 인스턴스
judge = MetricsJudge() 