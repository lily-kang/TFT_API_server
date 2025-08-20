"""프롬프트 템플릿 빌더"""

from typing import Dict, Any, Optional, List
from models.request import MasterMetrics, ToleranceAbs, ToleranceRatio
from config.prompts import SYNTAX_FIXING_PROMPT, LEXICAL_FIXING_PROMPT, CANDIDATE_SELECTION_PROMPT
from utils.logging import logger


class PromptBuilder:
    """LLM 프롬프트 구성 클래스"""
    
    def build_syntax_prompt(
        self,
        text: str,
        master: MasterMetrics,
        tolerance_abs: ToleranceAbs,
        tolerance_ratio: ToleranceRatio,
        current_metrics: Dict[str, float],
        problematic_metric: str,
        num_modifications: int,
        referential_clauses: str = ""
    ) -> str:
        """
        구문 수정용 프롬프트 구성
        
        Args:
            text: 수정할 텍스트
            master: 마스터 지표
            tolerance_abs: 절대값 허용 오차
            tolerance_ratio: 비율 허용 오차
            current_metrics: 현재 지표값들
            problematic_metric: 문제가 있는 지표명
            num_modifications: 수정할 문장 수 (고정값 3 사용)
            referential_clauses: 참조용 절 정보
            
        Returns:
            구성된 프롬프트 문자열
        """
        try:
            # 목표 범위 계산
            if 'length' in problematic_metric.lower():
                target_min = master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                target_max = master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
                target_range_length = f"{target_min:.2f} - {target_max:.2f}"
            else:
                target_range_length = f"N/A"
            
            if 'clause' in problematic_metric.lower() or 'embedded' in problematic_metric.lower():
                clause_tolerance = master.All_Embedded_Clauses_Ratio * tolerance_ratio.All_Embedded_Clauses_Ratio
                target_min = master.All_Embedded_Clauses_Ratio - clause_tolerance
                target_max = master.All_Embedded_Clauses_Ratio + clause_tolerance
                target_range_clauses = f"{target_min:.3f} - {target_max:.3f}"
            else:
                target_range_clauses = f"N/A"
            
            # 고정값 3으로 설정 (사용자 요청)
            fixed_num_modifications = 3
            
            # 프롬프트 변수 매핑
            prompt_vars = {
                'var_Generated_Passage': text,
                'var_problematic_metric': problematic_metric,
                'var_num_modifications': str(fixed_num_modifications),  # 고정값 3
                'var_current_value_avg_sentence_length': f"{current_metrics.get('avg_sentence_length', 0):.2f}",
                'var_target_range_avg_sentence_length': target_range_length,
                'var_current_value_embedded_clauses_ratio': f"{current_metrics.get('embedded_clauses_ratio', 0):.3f}",
                'var_target_range_embedded_clauses_ratio': target_range_clauses,
                'var_referential_clauses': referential_clauses or "No referential clauses provided."
            }
            
            # 프롬프트 템플릿에 변수 삽입
            prompt = SYNTAX_FIXING_PROMPT
            for var_name, var_value in prompt_vars.items():
                prompt = prompt.replace(f"{{{var_name}}}", str(var_value))
            
            logger.info(f"구문 수정 프롬프트 생성 완료 (문제 지표: {problematic_metric}, 수정 수: {fixed_num_modifications})")
            return prompt
            
        except Exception as e:
            logger.error(f"구문 프롬프트 생성 실패: {str(e)}")
            raise
    
    def build_lexical_prompt(
        self,
        text: str,
        master: MasterMetrics,
        tolerance_ratio: ToleranceRatio,
        current_metrics: Dict[str, float]
    ) -> str:
        """
        어휘 수정용 프롬프트 구성
        
        Args:
            text: 수정할 텍스트
            master: 마스터 지표
            tolerance_ratio: 비율 허용 오차
            current_metrics: 현재 지표값들
            
        Returns:
            구성된 프롬프트 문자열
        """
        try:
            # 어휘 목표 범위 계산
            lexical_tolerance = master.CEFR_NVJD_A1A2_lemma_ratio * tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio
            min_lexical = master.CEFR_NVJD_A1A2_lemma_ratio - lexical_tolerance
            max_lexical = master.CEFR_NVJD_A1A2_lemma_ratio + lexical_tolerance
            
            # 프롬프트 변수 매핑
            prompt_vars = {
                'original_text': text,
                'target_lexical_ratio': f"{master.CEFR_NVJD_A1A2_lemma_ratio:.3f}",
                'min_lexical': f"{min_lexical:.3f}",
                'max_lexical': f"{max_lexical:.3f}"
            }
            
            # 프롬프트 템플릿에 변수 삽입
            prompt = LEXICAL_FIXING_PROMPT
            for var_name, var_value in prompt_vars.items():
                prompt = prompt.replace(f"{{{var_name}}}", str(var_value))
            
            logger.info(f"어휘 수정 프롬프트 생성 완료")
            return prompt
            
        except Exception as e:
            logger.error(f"어휘 프롬프트 생성 실패: {str(e)}")
            raise
    
    def build_selection_prompt(
        self,
        candidates: List[str]
    ) -> str:
        """
        후보 선택용 프롬프트 구성 (범용)
        
        Args:
            candidates: 후보 텍스트 리스트
            
        Returns:
            구성된 프롬프트 문자열
        """
        try:
            if not candidates:
                raise ValueError("후보 리스트가 비어있습니다")
            
            # 후보 개수에 따라 동적으로 프롬프트 생성
            num_candidates = len(candidates)
            
            # 기본 프롬프트 템플릿
            base_prompt = """You are a precise text evaluator selecting the single best revised text from a list.

### Candidates"""
            
            # 후보들 추가
            for i, candidate in enumerate(candidates, 1):
                base_prompt += f"\ncandidate_{i}: {candidate}"
            
            # 평가 기준 추가
            base_prompt += """

### Evaluation Criteria (Strict Order):
1. **Foundational Correctness (Pass/Fail):** A candidate MUST be grammatically perfect AND perfectly preserve the original meaning. Any candidate that fails on either of these points is INSTANTLY DISQUALIFIED.
2. **Naturalness and Readability:** Among the candidates that pass Rule #1, the one that is most fluent and natural is better.
3. **Tie-Breaker:** If multiple candidates are equally good, choose the one that integrates its changes most elegantly.

### Response Format:
Respond ONLY with the number of the best candidate (1 to {num_candidates}).

Examples:"""
            
            # 예시 추가
            for i in range(1, min(num_candidates + 1, 4)):  # 최대 3개 예시까지만
                base_prompt += f"\n- If candidate {i} is best: \"{i}\""
            
            if num_candidates > 3:
                base_prompt += f"\n- If candidate {num_candidates} is best: \"{num_candidates}\""
            
            base_prompt += f"""

Do not include any explanation, JSON, or additional text. Just the number between 1 and {num_candidates}."""
            
            logger.info(f"후보 선택 프롬프트 생성 완료 ({num_candidates}개 후보)")
            return base_prompt
            
        except Exception as e:
            logger.error(f"선택 프롬프트 생성 실패: {str(e)}")
            raise
    
    def determine_problematic_metric(
        self,
        current_metrics: Dict[str, float],
        master: MasterMetrics,
        tolerance_abs: ToleranceAbs,
        tolerance_ratio: ToleranceRatio
    ) -> Optional[str]:
        """
        문제가 있는 지표 결정
        
        Args:
            current_metrics: 현재 지표값들
            master: 마스터 지표
            tolerance_abs: 절대값 허용 오차
            tolerance_ratio: 비율 허용 오차
            
        Returns:
            문제가 있는 지표명 또는 None
        """
        try:
            # 평균 문장 길이 확인
            avg_length = current_metrics.get('avg_sentence_length', 0)
            length_min = master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
            length_max = master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
            
            # 내포절 비율 확인
            clause_ratio = current_metrics.get('embedded_clauses_ratio', 0)
            clause_tolerance = master.All_Embedded_Clauses_Ratio * tolerance_ratio.All_Embedded_Clauses_Ratio
            clause_min = master.All_Embedded_Clauses_Ratio - clause_tolerance
            clause_max = master.All_Embedded_Clauses_Ratio + clause_tolerance
            
            # 우선순위: 내포절 비율 > 평균 문장 길이
            if not (clause_min <= clause_ratio <= clause_max):
                return "all_embedded_clauses_ratio"
            elif not (length_min <= avg_length <= length_max):
                return "avg_sentence_length"
            
            return None
            
        except Exception as e:
            logger.error(f"문제 지표 결정 실패: {str(e)}")
            return None
    
    def calculate_modification_count(
        self,
        text: str,
        problematic_metric: str,
        current_value: float,
        target_min: float,
        target_max: float
    ) -> int:
        """
        수정할 문장 수 계산 (고정값 3 반환)
        
        Args:
            text: 분석할 텍스트
            problematic_metric: 문제 지표명
            current_value: 현재 값
            target_min: 목표 최소값
            target_max: 목표 최대값
            
        Returns:
            수정할 문장 수 (고정값 3)
        """
        # 사용자 요청에 따라 고정값 3 반환
        return 3


# 전역 프롬프트 빌더 인스턴스
prompt_builder = PromptBuilder() 