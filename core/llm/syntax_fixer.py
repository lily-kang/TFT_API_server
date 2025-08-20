from typing import List, Tuple, Dict
from core.llm.client import llm_client
from core.llm.selector import CandidateSelector
from core.llm.prompt_builder import prompt_builder
from core.analyzer import analyzer
from core.metrics import metrics_extractor
from core.judge import judge
from config.settings import settings
from models.request import MasterMetrics, ToleranceAbs, ToleranceRatio
from models.internal import LLMCandidate, LLMResponse
from utils.exceptions import LLMAPIError
from utils.logging import logger


class SyntaxFixer:
    """구문 수정 클래스"""
    
    def __init__(self):
        self.selector = CandidateSelector()
        self.temperatures = settings.llm_temperatures  # [0.2, 0.3]
        self.candidates_per_temperature = settings.syntax_candidates_per_temperature  # 2
    
    async def preview_prompt(
        self,
        text: str,
        master: MasterMetrics,
        tolerance_abs: ToleranceAbs,
        tolerance_ratio: ToleranceRatio,
        current_metrics: Dict[str, float],
        referential_clauses: str = ""
    ) -> str:
        """
        프롬프트 미리보기 - LLM 호출 없이 프롬프트만 생성하여 반환
        
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
            logger.info(f"프롬프트 미리보기 시작: {len(text)} 글자")
            
            # current_metrics 키 이름 매핑
            mapped_metrics = {
                'avg_sentence_length': current_metrics.get('AVG_SENTENCE_LENGTH', 0),
                'embedded_clauses_ratio': current_metrics.get('All_Embedded_Clauses_Ratio', 0)
            }
            
            # 문제 지표 결정
            problematic_metric = prompt_builder.determine_problematic_metric(
                mapped_metrics, master, tolerance_abs, tolerance_ratio
            )
            
            if not problematic_metric:
                logger.info("문제가 있는 지표가 없어 프롬프트 생성 불가")
                return "문제가 있는 지표가 없습니다."
            
            # 수정 문장 수 계산
            current_value = mapped_metrics.get(
                'avg_sentence_length' if 'length' in problematic_metric else 'embedded_clauses_ratio', 0
            )
            
            if 'length' in problematic_metric:
                target_min = master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                target_max = master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
            else:
                clause_tolerance = master.All_Embedded_Clauses_Ratio * tolerance_ratio.All_Embedded_Clauses_Ratio
                target_min = master.All_Embedded_Clauses_Ratio - clause_tolerance
                target_max = master.All_Embedded_Clauses_Ratio + clause_tolerance
            
            num_modifications = prompt_builder.calculate_modification_count(
                text, problematic_metric, current_value, target_min, target_max
            )
            
            # 프롬프트 준비
            prompt = prompt_builder.build_syntax_prompt(
                text, master, tolerance_abs, tolerance_ratio,
                mapped_metrics, problematic_metric, num_modifications, referential_clauses
            )
            
            logger.info(f"프롬프트 미리보기 완료 (문제 지표: {problematic_metric})")
            return prompt
            
        except Exception as e:
            logger.error(f"프롬프트 미리보기 실패: {str(e)}")
            raise LLMAPIError(f"프롬프트 미리보기 중 오류 발생: {str(e)}")

    async def fix_syntax(
        self,
        text: str,
        master: MasterMetrics,
        tolerance_abs: ToleranceAbs,
        tolerance_ratio: ToleranceRatio,
        current_metrics: Dict[str, float],
        referential_clauses: str = "",
        n_candidates: int = 4  # 기본값: 2 temperatures × 2 candidates = 4
    ) -> Tuple[List[str], str]:
        """
        구문 수정을 수행합니다.
        
        Args:
            text: 수정할 텍스트
            master: 마스터 지표
            tolerance_abs: 절대값 허용 오차
            tolerance_ratio: 비율 허용 오차
            current_metrics: 현재 지표값들
            referential_clauses: 참조용 절 정보
            n_candidates: 생성할 후보 개수 (무시됨 - temperature 설정 우선)
            
        Returns:
            (후보 리스트, 선택된 텍스트) 튜플
            
        Raises:
            LLMAPIError: LLM 호출 실패 시
        """
        try:
            logger.info(f"구문 수정 시작: {len(text)} 글자")
            logger.info(f"Temperature 설정: {self.temperatures}, 각 temperature별 {self.candidates_per_temperature}개 후보")
            
            # current_metrics 키 이름 매핑
            mapped_metrics = {
                'avg_sentence_length': current_metrics.get('AVG_SENTENCE_LENGTH', 0),
                'embedded_clauses_ratio': current_metrics.get('All_Embedded_Clauses_Ratio', 0)
            }
            
            # 문제 지표 결정
            problematic_metric = prompt_builder.determine_problematic_metric(
                mapped_metrics, master, tolerance_abs, tolerance_ratio
            )
            
            if not problematic_metric:
                logger.info("문제가 있는 지표가 없어 원본 텍스트 반환")
                return [text], text
            
            # 수정 문장 수 계산
            current_value = mapped_metrics.get(
                'avg_sentence_length' if 'length' in problematic_metric else 'embedded_clauses_ratio', 0
            )
            
            if 'length' in problematic_metric:
                target_min = master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                target_max = master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
            else:
                clause_tolerance = master.All_Embedded_Clauses_Ratio * tolerance_ratio.All_Embedded_Clauses_Ratio
                target_min = master.All_Embedded_Clauses_Ratio - clause_tolerance
                target_max = master.All_Embedded_Clauses_Ratio + clause_tolerance
            
            num_modifications = prompt_builder.calculate_modification_count(
                text, problematic_metric, current_value, target_min, target_max
            )
            
            # 프롬프트 준비
            prompt = prompt_builder.build_syntax_prompt(
                text, master, tolerance_abs, tolerance_ratio,
                mapped_metrics, problematic_metric, num_modifications, referential_clauses
            )
            print(prompt)
            # 각 temperature별로 여러 후보 생성
            candidates = await llm_client.generate_multiple_per_temperature(
                prompt, 
                self.temperatures, 
                self.candidates_per_temperature
            )
            
            total_candidates = len(self.temperatures) * self.candidates_per_temperature
            logger.info(f"LLM으로 총 {len(candidates)}개 후보 생성 완료 (예상: {total_candidates}개)")
            
            # 각 후보를 분석기로 검증
            valid_candidates = []
            for i, candidate in enumerate(candidates):
                try:
                    # Temperature별 정보 계산
                    temp_index = i // self.candidates_per_temperature
                    candidate_index_in_temp = (i % self.candidates_per_temperature) + 1
                    temp_value = self.temperatures[temp_index] if temp_index < len(self.temperatures) else "Unknown"
                    
                    logger.info(f"후보 {i+1} 분석 중... (temp={temp_value}, {candidate_index_in_temp}/{self.candidates_per_temperature})")
                    
                    # 후보 텍스트 분석
                    raw_analysis = await analyzer.analyze(candidate, include_syntax=True)
                    candidate_metrics = metrics_extractor.extract(raw_analysis)
                    candidate_evaluation = judge.evaluate(candidate_metrics, master, tolerance_abs, tolerance_ratio)
                    
                    # 구문 지표 통과 여부 확인
                    if candidate_evaluation.syntax_pass == "PASS":
                        valid_candidates.append({
                            'text': candidate,
                            'index': i + 1,
                            'temperature': temp_value,
                            'temp_candidate_num': candidate_index_in_temp,
                            'metrics': candidate_metrics,
                            'evaluation': candidate_evaluation
                        })
                        logger.info(f"후보 {i+1}: 구문 지표 통과 ✅ (temp={temp_value})")
                    else:
                        logger.info(f"후보 {i+1}: 구문 지표 실패 ❌ (temp={temp_value})")
                        
                except Exception as e:
                    logger.warning(f"후보 {i+1} 분석 실패: {str(e)}")
                    continue
            
            # 통과한 후보가 없으면 실패
            if not valid_candidates:
                logger.warning("모든 후보가 구문 지표를 통과하지 못함")
                raise LLMAPIError("생성된 모든 후보가 구문 지표 요구사항을 만족하지 않습니다")
            
            logger.info(f"{len(valid_candidates)}개 후보가 구문 지표 통과")
            
            # 통과한 후보들 중에서 최적 선택
            if len(valid_candidates) == 1:
                selected_candidate = valid_candidates[0]
                logger.info(f"후보 {selected_candidate['index']}번만 통과하여 자동 선택 (temp={selected_candidate['temperature']})")
            else:
                # 여러 후보 중 LLM이 선택
                candidate_texts = [item['text'] for item in valid_candidates]
                selected_text = await self.selector.select_best(candidate_texts)
                
                # 선택된 텍스트에 해당하는 후보 찾기
                selected_candidate = None
                for candidate in valid_candidates:
                    if candidate['text'] == selected_text:
                        selected_candidate = candidate
                        break
                
                if not selected_candidate:
                    # 선택 실패 시 첫 번째 통과 후보 사용
                    selected_candidate = valid_candidates[0]
                    logger.warning("선택 실패로 첫 번째 통과 후보 사용")
                
                logger.info(f"LLM이 후보 {selected_candidate['index']}번 선택 (temp={selected_candidate['temperature']})")
            
            # 선택된 후보의 상세 지표 로깅
            selected_metrics = selected_candidate['metrics']
            logger.info(f"선택된 후보 지표: 평균문장길이={selected_metrics.AVG_SENTENCE_LENGTH:.2f}, "
                       f"내포절비율={selected_metrics.All_Embedded_Clauses_Ratio:.3f}")
            
            # 모든 후보와 선택된 텍스트 반환
            all_candidate_texts = [item['text'] for item in valid_candidates]
            selected_text = selected_candidate['text']
            selected_metrics = selected_candidate['metrics']
            selected_evaluation = selected_candidate['evaluation']
            
            logger.info(f"구문 수정 완료: {len(candidates)}개 생성 → {len(valid_candidates)}개 통과 → 1개 선택 (문제 지표: {problematic_metric})")
            return all_candidate_texts, selected_text, selected_metrics, selected_evaluation
            
        except Exception as e:
            logger.error(f"구문 수정 실패: {str(e)}")
            raise LLMAPIError(f"구문 수정 중 오류 발생: {str(e)}")


# 전역 구문 수정기 인스턴스
syntax_fixer = SyntaxFixer() 