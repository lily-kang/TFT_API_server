"""프롬프트 템플릿 빌더"""

import math
import json
from typing import Dict, Any, Optional, List
from models.request import MasterMetrics, ToleranceAbs, ToleranceRatio
from config.syntax_revision_prompt import SYNTAX_USER_INPUT_TEMPLATE, SYNTAX_PROMPT_DECREASE, SYNTAX_PROMPT_INCREASE, CANDIDATE_SELECTION_PROMPT
from config.lexical_revision_prompt import Lexical_USER_INPUT_TEMPLATE, LEXICAL_FIXING_PROMPT_DECREASE, LEXICAL_FIXING_PROMPT_INCREASE
from utils.logging import logger

class PromptBuilder:
    """LLM 프롬프트 구성 클래스"""
    
    def format_cefr_breakdown(self, cefr_breakdown: Any) -> str:
        """
        CEFR breakdown 객체를 프롬프트용 문자열로 변환
        
        Args:
            cefr_breakdown: CEFR breakdown 객체 (dict, list, 또는 기타 구조)
            
        Returns:
            프롬프트에 사용할 문자열
        """
        try:
            if isinstance(cefr_breakdown, str):
                # 이미 문자열이면 그대로 반환
                return cefr_breakdown
            elif isinstance(cefr_breakdown, dict):
                # 딕셔너리인 경우 보기 좋게 포맷팅
                formatted_lines = []
                for level, words in cefr_breakdown.items():
                    if isinstance(words, list):
                        word_list = ", ".join(words)
                        formatted_lines.append(f"{level}: {word_list}")
                    else:
                        formatted_lines.append(f"{level}: {words}")
                return "\n".join(formatted_lines)
            elif isinstance(cefr_breakdown, list):
                # 리스트인 경우 JSON 형태로 변환
                return json.dumps(cefr_breakdown, indent=2, ensure_ascii=False)
            else:
                # 기타 객체인 경우 JSON으로 변환 시도
                return json.dumps(cefr_breakdown, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"CEFR breakdown 변환 실패: {str(e)}, 원본 반환")
            return str(cefr_breakdown)
    
    # def build_syntax_prompt(
    #     self,
    #     text: str,
    #     target_min: float,
    #     target_max: float,
    #     current_metrics: Dict[str, float],
    #     problematic_metric: str,
    #     num_modifications: int,
    #     referential_clauses: str = "",
    #     prompt_type: str = "increase"  # "increase" or "decrease"
    # ) -> str:
    #     """
    #     구문 수정용 프롬프트 구성
        
    #     Args:
    #         text: 수정할 텍스트
    #         master: 마스터 지표
    #         tolerance_abs: 절대값 허용 오차
    #         tolerance_ratio: 비율 허용 오차
    #         current_metrics: 현재 지표값들
    #         problematic_metric: 문제가 있는 지표명
    #         num_modifications: 수정할 문장 수
    #         referential_clauses: 참조용 절 정보
    #         prompt_type: 프롬프트 타입 ("increase" 또는 "decrease")
            
    #     Returns:
    #         구성된 프롬프트 문자열
    #     """
    #     try:
    #         # prompt_type에 따라 기본 프롬프트 선택
    #         if prompt_type == "increase":
    #             prompt = SYNTAX_PROMPT_INCREASE
    #             logger.info(f"🔺 INCREASE 프롬프트 선택됨")
    #         elif prompt_type == "decrease":
    #             prompt = SYNTAX_PROMPT_DECREASE
    #             logger.info(f"🔻 DECREASE 프롬프트 선택됨")
    #         else:
    #             prompt = SYNTAX_PROMPT_DECREASE  # 기본값
    #             logger.warning(f"⚠️ 알 수 없는 prompt_type: {prompt_type}, DECREASE 사용")
            
            
    #         # 프롬프트 변수 매핑
    #         prompt_vars = {
    #             'var_Generated_Passage': text,
    #             'var_problematic_metric': problematic_metric,
    #             'var_num_modifications': str(num_modifications),
    #             'var_referential_clauses': referential_clauses or "No referential clauses provided.",
    #             'var_current_value_embedded_clauses_ratio' : current_metrics.get('all_embedded_clauses_ratio', 0),
    #             'var_target_range_embedded_clauses_ratio' : f"[{target_min:.3f} ~ {target_max:.3f}]",
    #         }
            
    #         # 프롬프트 템플릿에 변수 삽입
    #         for var_name, var_value in prompt_vars.items():
    #             prompt = prompt.replace(f"{{{var_name}}}", str(var_value))
            
    #         logger.info(f"구문 수정 프롬프트 생성 완료 (문제 지표: {problematic_metric}, 수정 수: {num_modifications}, 타입: {prompt_type})")
    #         return prompt
            
    #     except Exception as e:
    #         logger.error(f"구문 프롬프트 생성 실패: {str(e)}")
    #         raise
    
    def build_syntax_prompt(
        self,
        text: str,
        avg_target_min: float,
        avg_target_max: float,
        clause_target_min: float,
        clause_target_max: float,
        current_metrics: Dict[str, float],
        problematic_metric: str,
        num_modifications: int,
        referential_clauses: str = "",
        prompt_type: str = "increase"
    ) -> List[Dict[str, str]]:
        """
        구문 수정용 prompt (시스템+유저) 구성
        """
        try:
            # 시스템 프롬프트 선택
            if prompt_type == "increase":
                system_prompt = SYNTAX_PROMPT_INCREASE
            elif prompt_type == "decrease":
                system_prompt = SYNTAX_PROMPT_DECREASE
            else:
                system_prompt = SYNTAX_PROMPT_DECREASE

            # 메시지 변수 준비 - 각 지표별로 개별 표시
            avg_current = current_metrics.get('avg_sentence_length', 0)
            clause_current = current_metrics.get('all_embedded_clauses_ratio', 0)
            
            current_and_target_values = f"""
            - average sentence length
            current value: {avg_current:.3f} target range: [{avg_target_min:.3f} ~ {avg_target_max:.3f}]
            - embedded clause ratio
            current value: {clause_current:.3f} target range: [{clause_target_min:.3f} ~ {clause_target_max:.3f}]
            """

            user_vars = {
                'var_Generated_Passage': text,
                'var_problematic_metric': problematic_metric,
                'var_num_modifications': str(num_modifications),
                'var_referential_clauses': referential_clauses or "No referential clauses provided.",
                'var_current_values': current_and_target_values
            }

            user_prompt = SYNTAX_USER_INPUT_TEMPLATE
            for var_name, var_value in user_vars.items():
                user_prompt = user_prompt.replace(f"{{{var_name}}}", str(var_value))
            
            return [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        except Exception as e:
            logger.error(f"구문 프롬프트 생성 실패: {str(e)}")
            raise
    
    # def build_lexical_prompt(
    #     self,
    #     text: str,
    #     master: MasterMetrics,
    #     tolerance_ratio: ToleranceRatio,
    #     current_metrics: Dict[str, float],
        
    #     # prompt_type: str,  # "INCREASE" or "DECREASE"
    #     num_modifications: int = 3
    # ) -> str:
    #     """
    #     어휘 수정용 프롬프트 구성
        
    #     Args:
    #         text: 수정할 텍스트
    #         master: 마스터 지표
    #         tolerance_ratio: 비율 허용 오차
    #         current_metrics: 현재 지표값들
    #         cefr_breakdown: CEFR 어휘 분석 결과
    #         target_level: 목표 어휘 레벨 (A1/A2 또는 B1/B2)
    #         prompt_type: 프롬프트 타입 ("INCREASE" 또는 "DECREASE")
    #         num_modifications: 수정할 어휘 개수
            
    #     Returns:
    #         구성된 프롬프트 문자열
    #     """
    #     try:
    #         # CEFR breakdown 객체를 문자열로 변환
    #         cefr_breakdown_str = self.format_cefr_breakdown(cefr_breakdown) if cefr_breakdown else ""
            
    #         # 프롬프트 템플릿 선택
    #         if prompt_type == "DECREASE":
    #             # A1A2 비율을 낮춰야 함 (A1/A2 → B1/B2)
    #             template = LEXICAL_FIXING_PROMPT_DECREASE
    #             logger.info("DECREASE 프롬프트 템플릿 선택 (A1/A2 → B1/B2)")
    #         elif prompt_type == "INCREASE":
    #             # A1A2 비율을 높여야 함 (B1+ → A1/A2)
    #             template = LEXICAL_FIXING_PROMPT_INCREASE
    #             logger.info("INCREASE 프롬프트 템플릿 선택 (B1+ → A1/A2)")
    #         else:
    #             raise ValueError(f"지원하지 않는 prompt_type: {prompt_type}. 'INCREASE' 또는 'DECREASE'여야 합니다.")
            
    #         # 프롬프트 변수 매핑 (템플릿에 맞춘 변수명 사용)
    #         prompt_vars = {
    #             'var_generated_passage': text,
    #             'var_cefr_breakdown': cefr_breakdown_str,
    #             'var_num_modifications': str(num_modifications),
    #             'var_target_level': target_level
    #         }
            
    #         # 프롬프트 템플릿에 변수 삽입
    #         prompt = template
    #         for var_name, var_value in prompt_vars.items():
    #             prompt = prompt.replace(f"${{{var_name}}}", str(var_value))
            
    #         logger.info(f"어휘 수정 프롬프트 생성 완료 ({prompt_type})")
    #         return prompt
            
    #     except Exception as e:
    #         logger.error(f"어휘 프롬프트 생성 실패: {str(e)}")
    #         raise
    
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
            # clause_tolerance = master.All_Embedded_Clauses_Ratio * tolerance_ratio.All_Embedded_Clauses_Ratio
            clause_min = master.All_Embedded_Clauses_Ratio - tolerance_ratio.All_Embedded_Clauses_Ratio
            clause_max = master.All_Embedded_Clauses_Ratio + tolerance_ratio.All_Embedded_Clauses_Ratio
            
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
        # text: str,
        problematic_metric: str,
        current_value: float,
        target_min: float,
        target_max: float,
        analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        수정할 문장 수와 프롬프트 타입 계산 (동적 계산)
        
        Args:
            text: 분석할 텍스트
            problematic_metric: 문제 지표명
            current_value: 현재 값
            target_min: 목표 최소값
            target_max: 목표 최대값
            analysis_result: 분석 결과 (sentence_count, lexical_tokens, clause 정보 등)
            
        Returns:
            {'num_modifications': int, 'prompt_type': str} 딕셔너리
        """
        try:
            # 분석 결과에서 필요한 값들 추출
            sentence_count = analysis_result.get('sentence_count', 0)
            lexical_tokens = analysis_result.get('lexical_tokens', 0)

            # 복문 문장 수 총합 계산

            total_clause_sentences = analysis_result.get('total_clause_sentences', 0)

            logger.info(f"🔍 수정 문장 수 계산 상세:")
            logger.info(f"  - sentence_count: {sentence_count}")
            logger.info(f"  - lexical_tokens: {lexical_tokens}")
            logger.info(f"  - total_clause_sentences: {total_clause_sentences}")
            logger.info(f"  - problematic_metric: {problematic_metric}")
            logger.info(f"  - current_value: {current_value:.3f}")
            logger.info(f"  - target_min: {target_min:.3f}, target_max: {target_max:.3f}")
            
            # prompt_type 결정
            if current_value < target_min:
                prompt_type = "increase"
                logger.info(f"🔺 현재값({current_value:.3f}) < 최소값({target_min:.3f}) → INCREASE 프롬프트 선택")
            elif current_value > target_max:
                prompt_type = "decrease"
                logger.info(f"🔻 현재값({current_value:.3f}) > 최대값({target_max:.3f}) → DECREASE 프롬프트 선택")
            else:
                prompt_type = "decrease"  # 범위 내에 있으면 기본값
                logger.info(f"⚪ 현재값이 범위 내에 있음 → 기본 DECREASE 프롬프트 선택")
            
            # 평균 문장 길이를 수정할 경우 
            if 'length' in problematic_metric.lower():
                logger.info(f"📏 평균 문장 길이 계산 시작")
                if current_value > target_max:
                    # 평균 문장 길이가 기준보다 큼 → 문장 수 decrease
                    upper_bound = target_max
                    num_modifications = math.ceil((lexical_tokens / upper_bound) - sentence_count)
                    logger.info(f"  - 현재값({current_value:.3f}) > 최대값({target_max:.3f})")
                    logger.info(f"  - 계산: ceil(({lexical_tokens} / {upper_bound:.3f}) - {sentence_count}) = {num_modifications}")
                else:
                    # 평균 문장 길이가 기준보다 작음 → 문장 수 increase
                    lower_bound = target_min
                    num_modifications = math.floor(sentence_count - (lexical_tokens / lower_bound))
                    logger.info(f"  - 현재값({current_value:.3f}) < 최소값({target_min:.3f})")
                    logger.info(f"  - 계산: floor({sentence_count} - ({lexical_tokens} / {lower_bound:.3f})) = {num_modifications}")

            # 복문 비율을 수정할 경우
            elif 'clause' in problematic_metric.lower() or 'embedded' in problematic_metric.lower():
                logger.info(f"🔗 복문 비율 계산 시작")
                if current_value > target_max:
                    # 복문 비율이 기준보다 큼 → 복문 줄여야 함
                    target_ratio_upper = target_max
                    num_modifications = math.ceil(
                        (total_clause_sentences - (target_ratio_upper * sentence_count)) / 
                        (1 + target_ratio_upper)
                    )
                    logger.info(f"  - 현재값({current_value:.3f}) > 최대값({target_max:.3f})")
                    logger.info(f"  - 계산: ceil(({total_clause_sentences} - ({target_ratio_upper:.3f} * {sentence_count})) / (1 + {target_ratio_upper:.3f})) = {num_modifications}")
                else:
                    # 복문 비율이 기준보다 작음 → 복문 늘려야 함
                    target_ratio_lower = target_min
                    num_modifications = math.ceil(
                        ((target_ratio_lower * sentence_count) - total_clause_sentences) / 
                        (1 + target_ratio_lower)
                    )
                    logger.info(f"  - 현재값({current_value:.3f}) < 최소값({target_min:.3f})")
                    logger.info(f"  - 계산: ceil((({target_ratio_lower:.3f} * {sentence_count}) - {total_clause_sentences}) / (1 + {target_ratio_lower:.3f})) = {num_modifications}")

            else:
                # 지정되지 않은 메트릭 → 기본값
                num_modifications = 3
                logger.info(f"⚠️  지정되지 않은 메트릭: {problematic_metric}, 기본값 3 사용")
            

            result = {
                'num_modifications': num_modifications,
                'prompt_type': prompt_type
            }
            
            logger.info(f"✅ 최종 결과: {result}")
            return result

        except Exception as e:
            logger.error(f"수정 문장 수 계산 실패: {str(e)}")
            return {'num_modifications': 3, 'prompt_type': 'increase'}  # 기본값 반환
    

    def calculate_lexical_modification_count_nvjd(
        self,
        current_ratio: float,
        nvjd_total_lemma_count: int,
        nvjd_a1a2_lemma_count: int,
        master,
        tolerance_ratio,
    ) -> Dict[str, object]:
        """NVJD 기반 어휘 수정 단어 수 계산 (분석기 호출 없이 사전 계산값 사용)
        Returns dict: { num_modifications, direction, target_lower, target_upper, case }
        direction: "increase" | "decrease" | "none"
        """
        # 목표 범위 계산 (절대값 ± tolerance)
        target_lower = master.CEFR_NVJD_A1A2_lemma_ratio - tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio
        target_upper = master.CEFR_NVJD_A1A2_lemma_ratio + tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio

        # 경계 처리
        total = max(1, int(nvjd_total_lemma_count or 0))
        a1a2 = max(0, int(nvjd_a1a2_lemma_count or 0))
        cur = float(current_ratio)

        if target_lower <= cur <= target_upper:
            return {
                "num_modifications": 0,
                "direction": "none",
                "target_lower": target_lower,
                "target_upper": target_upper,
                "case": "within",
            }

        if cur < target_lower:
            need = (target_lower * total) - a1a2
            mods = int(math.ceil(need))
            return {
                "num_modifications": mods,
                "direction": "increase",
                "target_lower": target_lower,
                "target_upper": target_upper,
                "case": "below",
            }

        # cur > target_upper
        allow = target_upper * total
        need_remove = a1a2 - allow
        mods = int(math.ceil(need_remove))
        return {
            "num_modifications": mods,
            "direction": "decrease",
            "target_lower": target_lower,
            "target_upper": target_upper,
            "case": "above",
        }
##___________________________________#
    def build_lexical_prompt(
        self,
        text: str,
        current_cefr_ratio: float,
        target_min: float,
        target_max: float,
        num_modifications: int,
        direction: str,
        cefr_breakdown: Optional[Dict[str, Any]] = None
    ) -> list:
        """어휘 수정 프롬프트 구성 (Lexical_USER_INPUT_TEMPLATE 사용)"""
        system_prompt = LEXICAL_FIXING_PROMPT_INCREASE if direction == "increase" else LEXICAL_FIXING_PROMPT_DECREASE
        formatted_text_json = self._format_lexical_text_with_metrics(text, current_cefr_ratio, target_min, target_max)
        processed_profile = self._generate_vocab_profile(cefr_breakdown or {}, direction)
        target_level = "A1/A2" if direction == "increase" else "B1/B2"

        user_prompt = Lexical_USER_INPUT_TEMPLATE.format(
            var_originalText=text,
            var_formattedTextJson=formatted_text_json,
            var_processedProfile=processed_profile,
            var_totalModifications=num_modifications,
            var_targetLevel=target_level
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def _format_lexical_text_with_metrics(
        self,
        text: str,
        current_ratio: float,
        target_min: float,
        target_max: float
    ) -> str:
        import json as _json
        # 간단한 문장 분할
        sentences = text.split('. ')
        if len(sentences) > 1:
            sentences = [s + '.' if not s.endswith('.') else s for s in sentences[:-1]] + [sentences[-1]]
        formatted_sentences = [{"sentence_number": i, "text": s.strip()} for i, s in enumerate(sentences, 1)]
        metrics_info = f"""
- cefr_a1+a2_NVJD_lemma_ratio:
- current value: {current_ratio:.1%}
- target range: {target_min:.1%}~{target_max:.1%}
"""
        return f"""
## Sentences (JSON format):
{_json.dumps(formatted_sentences, ensure_ascii=False, indent=2)}

## Current Metrics:
{metrics_info}
"""

    def _generate_vocab_profile(self, cefr_breakdown: Dict[str, Any], direction: str) -> str:
        """cefr_breakdown을 direction 기준으로 정제하여 출력 문자열 생성
        - decrease: B1+ (b1,b2,c1,c2)만 표시
        - increase: A1/A2/B1만 표시
        """
        try:
            buckets_increase = ["a1", "a2", "b1"]
            buckets_decrease = ["b1", "b2", "c1", "c2"]
            selected = buckets_increase if direction == "increase" else buckets_decrease

            lines: List[str] = []
            for key in selected:
                slot = cefr_breakdown.get(key) or {}
                lemma_count = slot.get("lemma_count", 0)
                lemma_list = slot.get("lemma_list", []) or []
                lines.append(f"## {key.upper()} Lemmas (count={lemma_count})")
                if lemma_list:
                    lines.extend([f"- {lemma}" for lemma in lemma_list])
            else:
                lines.append("- (none)")
                lines.append("")
            return "\n".join(lines).strip()
        except Exception as e:
            logger.warning(f"vocab profile 생성 실패: {str(e)}")
            return ""

# 전역 프롬프트 빌더 인스턴스
prompt_builder = PromptBuilder() 


if __name__ == "__main__":
    instance = PromptBuilder()
    instance.calculate_modification_count(
        problematic_metric="all_embedded_clauses_ratio",
        current_value=0.55,
        target_min=0.181,
        target_max=0.272,
        analysis_result={
            'sentence_count': 53,
            'lexical_tokens': 463,
            'total_clause_sentences': 12}
    )