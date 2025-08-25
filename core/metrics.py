from typing import Dict, Any
from models.internal import MetricsData
from utils.exceptions import MetricsExtractionError
from utils.logging import logger
import json


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
            logger.info("="*60)
            logger.info("📊 분석기 API 응답 상세 로깅 시작")
            logger.info("="*60)
            
            # 전체 응답 구조 로깅
            # logger.info(f"🔍 전체 응답 키: {list(raw_analysis.keys())}")
            
            # 실제 API 응답 구조에 맞게 수정
            data = raw_analysis.get("data", {})
            # logger.info(f"📋 data 키: {list(data.keys())}")
            
            text_statistics = data.get("text_statistics", {})
            # logger.info(f"📈 text_statistics 키: {list(text_statistics.keys())}")
            
            # 테이블 추출
            basic_overview = text_statistics.get("table_01_basic_overview", {})
            table_02 = text_statistics.get("table_02_detailed_tokens", {})
            syntax_analysis = text_statistics.get("table_10_syntax_analysis", {})
            table_11 = text_statistics.get("table_11_lemma_metrics", {})
            table_09 = text_statistics.get("table_09_pos_distribution", {})
            
            # 1. 평균 문장 길이
            avg_sentence_length = basic_overview.get("avg_sentence_length", 0.0)
            sentence_count = basic_overview.get("sentence_count", 1)
            logger.info(f"✅ avg_sentence_length: {avg_sentence_length}")
            logger.info(f"✅ sentence_count: {sentence_count}")
            
            # lexical_tokens 추출 (t2 테이블에서)
            lexical_tokens = table_02.get("lexical_tokens", 0)
            logger.info(f"✅ lexical_tokens: {lexical_tokens}")
            
            
            content_lemmas = table_02.get("content_lemmas", 0)
            propn_lemma_count = table_09.get("propn_lemma_count", 0)
            cefr_a1_count = table_11.get("cefr_a1_NVJD_lemma_count", 0)
            cefr_a2_count = table_11.get("cefr_a2_NVJD_lemma_count", 0)
            logger.info(f"📊 content_lemmas: {content_lemmas}, propn_count: {propn_lemma_count}")
            logger.info(f"📊 A1_count: {cefr_a1_count}, A2_count: {cefr_a2_count}")
            
            # 2. 내포절 비율 추출

            adverbial_sentences = syntax_analysis.get("adverbial_clause_sentences", 0)
            coordinate_sentences = syntax_analysis.get("coordinate_clause_sentences", 0)
            nominal_sentences = syntax_analysis.get("nominal_clause_sentences", 0)
            relative_sentences = syntax_analysis.get("relative_clause_sentences", 0)
            
            total_clause_sentences = adverbial_sentences + coordinate_sentences + nominal_sentences + relative_sentences
            all_embedded_clauses_ratio = total_clause_sentences / sentence_count if sentence_count > 0 else 0.0
            
            logger.info(f"📈 총 절 문장 수: {total_clause_sentences}")
            logger.info(f"📈 전체 문장 수: {sentence_count}")
            logger.info(f"✅ All_Embedded_Clauses_Ratio: {all_embedded_clauses_ratio}")
            
            # 3. CEFR A1A2 어휘 비율
            logger.info("\n" + "="*40)
            logger.info("📚 3. CEFR_NVJD_lemma_A1A2 어휘 비율")
            logger.info("="*40)
            
            
            # logger.info(f"🔍 table_11_lemma_metrics 전체 내용:")
            # logger.info(json.dumps(lemma_metrics, indent=2, ensure_ascii=False))
            
            cefr_a1_ratio = table_11.get("cefr_a1_NVJD_lemma_ratio", 0.0)
            cefr_a2_ratio = table_11.get("cefr_a2_NVJD_lemma_ratio", 0.0)
            cefr_a1a2_ratio = cefr_a1_ratio + cefr_a2_ratio
            
            # logger.info(f"📊 cefr_a1_NVJD_lemma_ratio: {cefr_a1_ratio}")
            # logger.info(f"📊 cefr_a2_NVJD_lemma_ratio: {cefr_a2_ratio}")
            logger.info(f"✅ CEFR_NVJD_A1A2_lemma_ratio: {cefr_a1a2_ratio}")
            
            # 최종 결과
            extracted = MetricsData(
                AVG_SENTENCE_LENGTH=round(float(avg_sentence_length), 3),
                All_Embedded_Clauses_Ratio=round(float(all_embedded_clauses_ratio), 3),
                CEFR_NVJD_A1A2_lemma_ratio=round(float(cefr_a1a2_ratio), 3)
            )
            
            logger.info("\n" + "="*60)
            logger.info("🎯 최종 추출된 지표")
            logger.info("="*60)
            logger.info(f"✅ AVG_SENTENCE_LENGTH: {extracted.AVG_SENTENCE_LENGTH:.3f}")
            logger.info(f"✅ All_Embedded_Clauses_Ratio: {extracted.All_Embedded_Clauses_Ratio:.3f}")
            logger.info(f"✅ CEFR_NVJD_A1A2_lemma_ratio: {extracted.CEFR_NVJD_A1A2_lemma_ratio:.3f}")
            logger.info("="*60)
            
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