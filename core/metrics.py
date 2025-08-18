from typing import Dict, Any
from models.internal import MetricsData
from utils.exceptions import MetricsExtractionError
from utils.logging import logger


class MetricsExtractor:
    """분석 결과에서 지표를 추출하는 클래스"""
    
    def extract(self, raw_analysis: Dict[str, Any]) -> MetricsData:
        """
        외부 분석기의 원시 결과에서 필요한 지표를 추출합니다.
        
        Args:
            raw_analysis: 외부 분석기 API 응답
            
        Returns:
            추출된 지표 데이터
            
        Raises:
            MetricsExtractionError: 지표 추출 실패 시
        """
        try:
            # TODO: 실제 외부 API 응답 구조에 맞게 수정 필요
            # 현재는 예상 구조로 작성
            metrics_data = raw_analysis.get("metrics", {})
            
            extracted = MetricsData(
                AVG_SENTENCE_LENGTH=metrics_data.get("AVG_SENTENCE_LENGTH", 0.0),
                All_Embedded_Clauses_Ratio=metrics_data.get("All_Embedded_Clauses_Ratio", 0.0),
                CEFR_NVJD_A1A2_lemma_ratio=metrics_data.get("CEFR_NVJD_A1A2_lemma_ratio", 0.0),
                AVG_CONTENT_SYLLABLES=metrics_data.get("AVG_CONTENT_SYLLABLES"),
                CL_CEFR_B1B2C1C2_ratio=metrics_data.get("CL_CEFR_B1B2C1C2_ratio"),
                PP_Weighted_Ratio=metrics_data.get("PP_Weighted_Ratio")
            )
            
            logger.info(f"지표 추출 완료: {extracted}")
            return extracted
            
        except Exception as e:
            logger.error(f"지표 추출 실패: {str(e)}")
            raise MetricsExtractionError(f"지표 추출 중 오류 발생: {str(e)}")
    
    def format_detailed_result(self, metrics: MetricsData, evaluation_result: Dict[str, Dict]) -> str:
        """
        상세 분석 결과를 포맷팅합니다.
        
        Args:
            metrics: 추출된 지표 데이터
            evaluation_result: 평가 결과 (지표별 상세 정보 포함)
            
        Returns:
            포맷팅된 상세 결과 문자열
        """
        result_lines = []
        
        for metric_name, detail in evaluation_result.items():
            if metric_name in ["syntax_pass", "lexical_pass"]:
                continue
                
            current_value = getattr(metrics, metric_name, None)
            if current_value is None:
                continue
                
            min_val = detail.get("min_value", 0)
            max_val = detail.get("max_value", 0)
            is_pass = detail.get("is_pass", False)
            status = "Pass" if is_pass else "Fail"
            
            line = f"{metric_name}: {current_value:.3f} vs [{min_val:.3f} ~ {max_val:.3f}] → {status}"
            result_lines.append(line)
        
        return "\n".join(result_lines)


# 전역 지표 추출기 인스턴스
metrics_extractor = MetricsExtractor() 