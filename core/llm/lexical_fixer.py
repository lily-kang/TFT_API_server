from typing import List, Tuple, Dict, Any
import asyncio
from core.llm.client import llm_client
from core.llm.selector import CandidateSelector
from core.llm.prompt_builder import prompt_builder
from core.analyzer import analyzer
from core.metrics import metrics_extractor
from core.judge import judge
from config.settings import settings
from models.request import MasterMetrics, ToleranceRatio
from utils.exceptions import LLMAPIError
from utils.logging import logger


class LexicalFixer:
    """어휘 수정 클래스"""
    
    def __init__(self):
        self.selector = CandidateSelector()
        self.temperatures = settings.llm_temperatures  # [0.2, 0.3]
        self.candidates_per_temperature =  2  # 기본값 2
    
    async def fix_lexical_with_params(
        self,
        text: str,
        master: MasterMetrics,
        tolerance_ratio: ToleranceRatio,
        current_metrics: Dict[str, float],
        target_level: str,  # API에서 입력되는 목표 레벨 (예: "A1/A2" 또는 "B1/B2")
        cefr_breakdown: Any,
        lexical_analysis_result: Dict[str, Any]
    ) -> Tuple[List[str], str, Any, Any, int]:
        """
        어휘 수정을 수행합니다.
        
        Args:
            text: 수정할 텍스트
            master: 마스터 지표
            tolerance_ratio: 비율 허용 오차
            current_metrics: 현재 지표값들
            target_level: API에서 입력되는 목표 레벨 (예: "A1/A2" 또는 "B1/B2")
            cefr_breakdown: CEFR 어휘 분석 결과 (객체)
            lexical_analysis_result: 어휘 수정용 분석 결과
            
        Returns:
            (후보 리스트, 선택된 텍스트, 최종 지표, 최종 평가, 전체 생성된 후보 수) 튜플
            
        Raises:
            LLMAPIError: LLM 호출 실패 시
        """
        try:
            logger.info(f"어휘 수정 시작: {len(text)} 글자")
            logger.info(f"Temperature 설정: {self.temperatures}, 각 temperature별 {self.candidates_per_temperature}개 후보")
            
            # 1. 현재 CEFR A1A2 비율과 목표 범위 계산
            current_ratio = current_metrics.get('cefr_nvjd_a1a2_lemma_ratio', 0)
            lexical_tolerance = master.CEFR_NVJD_A1A2_lemma_ratio * tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio
            target_min = master.CEFR_NVJD_A1A2_lemma_ratio - lexical_tolerance
            target_max = master.CEFR_NVJD_A1A2_lemma_ratio + lexical_tolerance
            
            logger.info(f"현재 A1A2 비율: {current_ratio:.3f}, 목표 범위: [{target_min:.3f}, {target_max:.3f}]")
            
            # 2. 프롬프트 타입 결정 (target_level은 API에서 제공받음)
            if current_ratio > target_max:
                # A1A2 비율이 너무 높음 → 낮춰야 함 (A1/A2 → B1/B2)
                prompt_type = "DECREASE"
                logger.info(f"A1A2 비율이 목표보다 높음 → DECREASE 프롬프트 사용")
            elif current_ratio < target_min:
                # A1A2 비율이 너무 낮음 → 높여야 함 (B1+ → A1/A2)
                prompt_type = "INCREASE"
                logger.info(f"A1A2 비율이 목표보다 낮음 → INCREASE 프롬프트 사용")
            else:
                # 이미 목표 범위 안에 있음
                logger.info("A1A2 비율이 이미 목표 범위 안에 있음")
                return [text], text, None, None, 0
            
            # 3. 수정할 어휘 개수 계산
            num_modifications = prompt_builder.calculate_lexical_modification_count(
                current_ratio, target_min, target_max, lexical_analysis_result
            )
            logger.info(f"계산된 수정 어휘 개수: {num_modifications}개")
            
            # 4. 프롬프트 준비
            prompt = prompt_builder.build_lexical_prompt(
                text, master, tolerance_ratio, current_metrics, 
                cefr_breakdown, target_level, prompt_type, num_modifications
            )
            logger.info(f"어휘 수정 프롬프트 생성 완료 ({prompt_type})")
            print(prompt)
            
            # 5. 각 temperature별로 여러 후보 생성
            candidates = await llm_client.generate_multiple_per_temperature(
                prompt, 
                self.temperatures, 
                self.candidates_per_temperature
            )
            
            total_candidates = len(self.temperatures) * self.candidates_per_temperature
            logger.info(f"LLM으로 총 {len(candidates)}개 후보 생성 완료 (예상: {total_candidates}개)")
            
            # 6. 각 후보를 분석기로 검증 (병렬 처리)
            logger.info(f"총 {len(candidates)}개 후보를 병렬로 분석 시작...")
            
            # 분석 태스크 생성
            analysis_tasks = []
            candidate_info = []
            
            for i, candidate in enumerate(candidates):
                # Temperature별 정보 계산
                temp_index = i // self.candidates_per_temperature
                candidate_index_in_temp = (i % self.candidates_per_temperature) + 1
                temp_value = self.temperatures[temp_index] if temp_index < len(self.temperatures) else "Unknown"
                
                # 분석 태스크 생성
                task = self._analyze_candidate(candidate, master, tolerance_ratio)
                analysis_tasks.append(task)
                candidate_info.append({
                    'index': i + 1,
                    'text': candidate,
                    'temperature': temp_value,
                    'temp_candidate_num': candidate_index_in_temp
                })
            
            # 7. 병렬 분석 실행
            try:
                analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
                logger.info(f"병렬 분석 완료: 총 {len(analysis_results)}개 결과")
                
                # 결과 처리
                valid_candidates = []
                for i, (result, info) in enumerate(zip(analysis_results, candidate_info)):
                    if isinstance(result, Exception):
                        logger.warning(f"후보 {info['index']} 분석 실패: {str(result)}")
                        continue
                    
                    candidate_metrics, candidate_evaluation = result
                    
                    # 어휘 지표 통과 여부 확인
                    if candidate_evaluation.lexical_pass == "PASS":
                        valid_candidates.append({
                            'text': info['text'],
                            'index': info['index'],
                            'temperature': info['temperature'],
                            'temp_candidate_num': info['temp_candidate_num'],
                            'metrics': candidate_metrics,
                            'evaluation': candidate_evaluation
                        })
                        logger.info(f"후보 {info['index']}: 어휘 지표 통과 ✅ (temp={info['temperature']})")
                        logger.info(f"   - CEFR A1A2 비율: {candidate_metrics.CEFR_NVJD_A1A2_lemma_ratio:.3f}")
                    else:
                        logger.info(f"후보 {info['index']}: 어휘 지표 실패 ❌ (temp={info['temperature']})")
                        logger.info(f"   - CEFR A1A2 비율: {candidate_metrics.CEFR_NVJD_A1A2_lemma_ratio:.3f} (목표: {target_min:.3f}-{target_max:.3f})")
                
            except Exception as e:
                logger.error(f"병렬 분석 중 예기치 못한 오류: {str(e)}")
                # 폴백: 순차 처리
                logger.info("폴백: 순차 처리로 재시도...")
                valid_candidates = await self._analyze_candidates_sequential(candidates, master, tolerance_ratio)
            
            # 8. 통과한 후보가 없으면 실패
            if not valid_candidates:
                logger.warning("모든 후보가 어휘 지표를 통과하지 못함")
                raise LLMAPIError("생성된 모든 후보가 어휘 지표 요구사항을 만족하지 않습니다")
            
            logger.info(f"{len(valid_candidates)}개 후보가 어휘 지표 통과")
            
            # 9. 통과한 후보들 중에서 최적 선택
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
            
            # 10. 선택된 후보의 상세 지표 로깅
            selected_metrics = selected_candidate['metrics']
            logger.info(f"선택된 후보 지표: CEFR A1A2 비율={selected_metrics.CEFR_NVJD_A1A2_lemma_ratio:.3f}")
            
            # 모든 후보와 선택된 텍스트 반환
            all_candidate_texts = [item['text'] for item in valid_candidates]
            selected_text = selected_candidate['text']
            selected_metrics = selected_candidate['metrics']
            selected_evaluation = selected_candidate['evaluation']
            
            # 전체 생성된 후보 수 계산
            total_candidates_generated = len(self.temperatures) * self.candidates_per_temperature
            
            logger.info(f"어휘 수정 완료: {total_candidates_generated}개 생성 → {len(valid_candidates)}개 통과 → 1개 선택 ({prompt_type})")
            return all_candidate_texts, selected_text, selected_metrics, selected_evaluation, total_candidates_generated
            
        except Exception as e:
            logger.error(f"어휘 수정 실패: {str(e)}")
            raise LLMAPIError(f"어휘 수정 중 오류 발생: {str(e)}")
    
    async def _analyze_candidate(self, candidate: str, master: MasterMetrics, tolerance_ratio: ToleranceRatio) -> Tuple[Any, Any]:
        """
        단일 후보를 분석하여 지표와 평가 결과를 반환합니다.
        
        Args:
            candidate: 분석할 텍스트
            master: 마스터 지표
            tolerance_ratio: 비율 허용 오차
            
        Returns:
            (지표, 평가 결과) 튜플
        """
        try:
            raw_analysis = await analyzer.analyze(candidate, include_syntax=False)  # 어휘만 분석
            candidate_metrics = metrics_extractor.extract(raw_analysis)
            candidate_evaluation = judge.evaluate(candidate_metrics, master, None, tolerance_ratio)  # tolerance_abs는 None
            return candidate_metrics, candidate_evaluation
        except Exception as e:
            logger.error(f"후보 분석 중 오류 발생: {str(e)}")
            raise e
    
    async def _analyze_candidates_sequential(self, candidates: List[str], master: MasterMetrics, tolerance_ratio: ToleranceRatio) -> List[Dict[str, Any]]:
        """
        순차적으로 후보를 분석하여 통과한 후보만 반환합니다.
        
        Args:
            candidates: 분석할 후보 텍스트 리스트
            master: 마스터 지표
            tolerance_ratio: 비율 허용 오차
            
        Returns:
            통과한 후보들의 정보를 담은 리스트
        """
        valid_candidates = []
        for i, candidate in enumerate(candidates):
            try:
                # Temperature별 정보 계산
                temp_index = i // self.candidates_per_temperature
                candidate_index_in_temp = (i % self.candidates_per_temperature) + 1
                temp_value = self.temperatures[temp_index] if temp_index < len(self.temperatures) else "Unknown"
                
                logger.info(f"후보 {i+1} 분석 중... (temp={temp_value}, {candidate_index_in_temp}/{self.candidates_per_temperature})")
                
                # 후보 텍스트 분석
                raw_analysis = await analyzer.analyze(candidate, include_syntax=False)  # 어휘만 분석
                candidate_metrics = metrics_extractor.extract(raw_analysis)
                candidate_evaluation = judge.evaluate(candidate_metrics, master, None, tolerance_ratio)
                
                # 어휘 지표 통과 여부 확인
                if candidate_evaluation.lexical_pass == "PASS":
                    valid_candidates.append({
                        'text': candidate,
                        'index': i + 1,
                        'temperature': temp_value,
                        'temp_candidate_num': candidate_index_in_temp,
                        'metrics': candidate_metrics,
                        'evaluation': candidate_evaluation
                    })
                    logger.info(f"후보 {i+1}: 어휘 지표 통과 ✅ (temp={temp_value})")
                    logger.info(f"   - CEFR A1A2 비율: {candidate_metrics.CEFR_NVJD_A1A2_lemma_ratio:.3f}")
                else:
                    logger.info(f"후보 {i+1}: 어휘 지표 실패 ❌ (temp={temp_value})")
                    logger.info(f"   - CEFR A1A2 비율: {candidate_metrics.CEFR_NVJD_A1A2_lemma_ratio:.3f}")
                    
            except Exception as e:
                logger.warning(f"후보 {i+1} 분석 실패: {str(e)}")
                continue
        return valid_candidates
    



# 전역 어휘 수정기 인스턴스
lexical_fixer = LexicalFixer() 