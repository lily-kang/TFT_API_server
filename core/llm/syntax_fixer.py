from typing import List, Tuple, Dict, Any
import asyncio
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
    

    async def fix_syntax_with_params(
        self,
        text: str,
        master: MasterMetrics,
        tolerance_abs: ToleranceAbs,
        tolerance_ratio: ToleranceRatio,
        current_metrics: Dict[str, float],
        num_modifications: int,
        problematic_metric: str,
        referential_clauses: str = ""
    ) -> Tuple[List[str], str, Any, Any, int]:
        """
        API에서 계산된 파라미터로 구문 수정을 수행합니다.
        
        Args:
            text: 수정할 텍스트
            master: 마스터 지표
            tolerance_abs: 절대값 허용 오차
            tolerance_ratio: 비율 허용 오차
            current_metrics: 현재 지표값들
            num_modifications: 수정할 문장 수 (API에서 자동 계산됨)
            problematic_metric: 문제가 있는 지표명 (API에서 자동 계산됨)
            referential_clauses: 참조용 절 정보
            
        Returns:
            (후보 리스트, 선택된 텍스트, 최종 지표, 최종 평가, 전체 생성된 후보 수) 튜플
            
        Raises:
            LLMAPIError: LLM 호출 실패 시
        """
        try:
            logger.info(f"구문 수정 시작 (API 계산된 파라미터 사용): {len(text)} 글자")
            logger.info(f"Temperature 설정: {self.temperatures}, 각 temperature별 {self.candidates_per_temperature}개 후보")
            logger.info(f"API 계산 결과 - 문제지표: {problematic_metric}, 수정수: {num_modifications}")
            
            # current_metrics 키 이름 매핑
            mapped_metrics = {
                'avg_sentence_length': current_metrics.get('AVG_SENTENCE_LENGTH', 0),
                'embedded_clauses_ratio': current_metrics.get('All_Embedded_Clauses_Ratio', 0)
            }
            
            # 프롬프트 준비 (API에서 계산된 파라미터 사용)
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
            
            # 생성된 후보들의 텍스트 내용 확인 (디버깅용)
            for i, candidate in enumerate(candidates):
                temp_index = i // self.candidates_per_temperature
                candidate_index_in_temp = (i % self.candidates_per_temperature) + 1
                temp_value = self.temperatures[temp_index] if temp_index < len(self.temperatures) else "Unknown"
                logger.info(f"=== 후보 {i+1} (temp={temp_value}, {candidate_index_in_temp}/{self.candidates_per_temperature}) ===")
                logger.info(f"길이: {len(candidate)}글자")
                logger.info(f"처음 100글자: {candidate[:100]}...")
                logger.info(f"마지막 100글자: ...{candidate[-100:]}")
                logger.info("=" * 60)
            
            # 각 후보를 분석기로 검증 (병렬 처리)
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
                task = self._analyze_candidate(candidate, master, tolerance_abs, tolerance_ratio)
                analysis_tasks.append(task)
                candidate_info.append({
                    'index': i + 1,
                    'text': candidate,
                    'temperature': temp_value,
                    'temp_candidate_num': candidate_index_in_temp
                })
            
            # 병렬 분석 실행
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
                    
                    # 구문 지표 통과 여부 확인
                    if candidate_evaluation.syntax_pass == "PASS":
                        valid_candidates.append({
                            'text': info['text'],
                            'index': info['index'],
                            'temperature': info['temperature'],
                            'temp_candidate_num': info['temp_candidate_num'],
                            'metrics': candidate_metrics,
                            'evaluation': candidate_evaluation
                        })
                        logger.info(f"후보 {info['index']}: 구문 지표 통과 ✅ (temp={info['temperature']})")
                        logger.info(f"   - 평균 문장 길이: {candidate_metrics.AVG_SENTENCE_LENGTH:.3f}")
                        logger.info(f"   - 내포절 비율: {candidate_metrics.All_Embedded_Clauses_Ratio:.3f}")
                    else:
                        # 목표 범위 계산 (로그용)
                        length_min = master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                        length_max = master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
                        clause_tolerance = master.All_Embedded_Clauses_Ratio * tolerance_ratio.All_Embedded_Clauses_Ratio
                        clause_min = master.All_Embedded_Clauses_Ratio - clause_tolerance
                        clause_max = master.All_Embedded_Clauses_Ratio + clause_tolerance
                        
                        logger.info(f"후보 {info['index']}: 구문 지표 실패 ❌ (temp={info['temperature']})")
                        logger.info(f"   - 평균 문장 길이: {candidate_metrics.AVG_SENTENCE_LENGTH:.3f} (목표: {length_min:.2f}-{length_max:.2f})")
                        logger.info(f"   - 내포절 비율: {candidate_metrics.All_Embedded_Clauses_Ratio:.3f} (목표: {clause_min:.3f}-{clause_max:.3f})")
                        
                        # 어떤 지표가 실패했는지 구체적으로 표시
                        length_pass = length_min <= candidate_metrics.AVG_SENTENCE_LENGTH <= length_max
                        clause_pass = clause_min <= candidate_metrics.All_Embedded_Clauses_Ratio <= clause_max
                        logger.info(f"   - 문장길이 통과: {'✅' if length_pass else '❌'}, 내포절 통과: {'✅' if clause_pass else '❌'}")
                
            except Exception as e:
                logger.error(f"병렬 분석 중 예기치 못한 오류: {str(e)}")
                # 폴백: 순차 처리
                logger.info("폴백: 순차 처리로 재시도...")
                valid_candidates = await self._analyze_candidates_sequential(candidates, master, tolerance_abs, tolerance_ratio)
            
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
            
            # 전체 생성된 후보 수 계산
            total_candidates_generated = len(self.temperatures) * self.candidates_per_temperature
            
            logger.info(f"구문 수정 완료: {total_candidates_generated}개 생성 → {len(valid_candidates)}개 통과 → 1개 선택 (문제 지표: {problematic_metric})")
            return all_candidate_texts, selected_text, selected_metrics, selected_evaluation, total_candidates_generated
            
        except Exception as e:
            logger.error(f"구문 수정 실패: {str(e)}")
            raise LLMAPIError(f"구문 수정 실패: {str(e)}")
    
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
            
            # 수정 문장 수는 API 요청에서 전달받으므로 고정값 3 사용
            num_modifications = 3
            
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
            
            # 각 후보를 분석기로 검증 (병렬 처리)
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
                task = self._analyze_candidate(candidate, master, tolerance_abs, tolerance_ratio)
                analysis_tasks.append(task)
                candidate_info.append({
                    'index': i + 1,
                    'text': candidate,
                    'temperature': temp_value,
                    'temp_candidate_num': candidate_index_in_temp
                })
            
            # 병렬 분석 실행
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
                    
                    # 구문 지표 통과 여부 확인
                    if candidate_evaluation.syntax_pass == "PASS":
                        valid_candidates.append({
                            'text': info['text'],
                            'index': info['index'],
                            'temperature': info['temperature'],
                            'temp_candidate_num': info['temp_candidate_num'],
                            'metrics': candidate_metrics,
                            'evaluation': candidate_evaluation
                        })
                        logger.info(f"후보 {info['index']}: 구문 지표 통과 ✅ (temp={info['temperature']})")
                        logger.info(f"   - 평균 문장 길이: {candidate_metrics.AVG_SENTENCE_LENGTH:.3f}")
                        logger.info(f"   - 내포절 비율: {candidate_metrics.All_Embedded_Clauses_Ratio:.3f}")
                    else:
                        # 목표 범위 계산 (로그용)
                        length_min = master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                        length_max = master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
                        clause_tolerance = master.All_Embedded_Clauses_Ratio * tolerance_ratio.All_Embedded_Clauses_Ratio
                        clause_min = master.All_Embedded_Clauses_Ratio - clause_tolerance
                        clause_max = master.All_Embedded_Clauses_Ratio + clause_tolerance
                        
                        logger.info(f"후보 {info['index']}: 구문 지표 실패 ❌ (temp={info['temperature']})")
                        logger.info(f"   - 평균 문장 길이: {candidate_metrics.AVG_SENTENCE_LENGTH:.3f} (목표: {length_min:.2f}-{length_max:.2f})")
                        logger.info(f"   - 내포절 비율: {candidate_metrics.All_Embedded_Clauses_Ratio:.3f} (목표: {clause_min:.3f}-{clause_max:.3f})")
                        
                        # 어떤 지표가 실패했는지 구체적으로 표시
                        length_pass = length_min <= candidate_metrics.AVG_SENTENCE_LENGTH <= length_max
                        clause_pass = clause_min <= candidate_metrics.All_Embedded_Clauses_Ratio <= clause_max
                        logger.info(f"   - 문장길이 통과: {'✅' if length_pass else '❌'}, 내포절 통과: {'✅' if clause_pass else '❌'}")
                
            except Exception as e:
                logger.error(f"병렬 분석 중 예기치 못한 오류: {str(e)}")
                # 폴백: 순차 처리
                logger.info("폴백: 순차 처리로 재시도...")
                valid_candidates = await self._analyze_candidates_sequential(candidates, master, tolerance_abs, tolerance_ratio)
            
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

    async def _analyze_candidate(self, candidate: str, master: MasterMetrics, tolerance_abs: ToleranceAbs, tolerance_ratio: ToleranceRatio) -> Tuple[Dict[str, float], Dict[str, str]]:
        """
        단일 후보를 분석하여 지표와 평가 결과를 반환합니다.
        
        Args:
            candidate: 분석할 텍스트
            master: 마스터 지표
            tolerance_abs: 절대값 허용 오차
            tolerance_ratio: 비율 허용 오차
            
        Returns:
            (지표 딕셔너리, 평가 결과 딕셔너리) 튜플
        """
        try:
            raw_analysis = await analyzer.analyze(candidate, include_syntax=True)
            candidate_metrics = metrics_extractor.extract(raw_analysis)
            candidate_evaluation = judge.evaluate(candidate_metrics, master, tolerance_abs, tolerance_ratio)
            return candidate_metrics, candidate_evaluation
        except Exception as e:
            logger.error(f"후보 분석 중 오류 발생: {str(e)}")
            raise e # 예외를 다시 발생시켜 병렬 처리에서 폴백되도록 함

    async def _analyze_candidates_sequential(self, candidates: List[str], master: MasterMetrics, tolerance_abs: ToleranceAbs, tolerance_ratio: ToleranceRatio) -> List[Dict[str, Any]]:
        """
        순차적으로 후보를 분석하여 통과한 후보만 반환합니다.
        
        Args:
            candidates: 분석할 후보 텍스트 리스트
            master: 마스터 지표
            tolerance_abs: 절대값 허용 오차
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
                    logger.info(f"   - 평균 문장 길이: {candidate_metrics.AVG_SENTENCE_LENGTH:.3f}")
                    logger.info(f"   - 내포절 비율: {candidate_metrics.All_Embedded_Clauses_Ratio:.3f}")
                else:
                    # 목표 범위 계산 (로그용)
                    length_min = master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
                    length_max = master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
                    clause_tolerance = master.All_Embedded_Clauses_Ratio * tolerance_ratio.All_Embedded_Clauses_Ratio
                    clause_min = master.All_Embedded_Clauses_Ratio - clause_tolerance
                    clause_max = master.All_Embedded_Clauses_Ratio + clause_tolerance
                    
                    logger.info(f"후보 {i+1}: 구문 지표 실패 ❌ (temp={temp_value})")
                    logger.info(f"   - 평균 문장 길이: {candidate_metrics.AVG_SENTENCE_LENGTH:.3f} (목표: {length_min:.2f}-{length_max:.2f})")
                    logger.info(f"   - 내포절 비율: {candidate_metrics.All_Embedded_Clauses_Ratio:.3f} (목표: {clause_min:.3f}-{clause_max:.3f})")
                    
                    # 어떤 지표가 실패했는지 구체적으로 표시
                    length_pass = length_min <= candidate_metrics.AVG_SENTENCE_LENGTH <= length_max
                    clause_pass = clause_min <= candidate_metrics.All_Embedded_Clauses_Ratio <= clause_max
                    logger.info(f"   - 문장길이 통과: {'✅' if length_pass else '❌'}, 내포절 통과: {'✅' if clause_pass else '❌'}")
                    
            except Exception as e:
                logger.warning(f"후보 {i+1} 분석 실패: {str(e)}")
                continue
        return valid_candidates


# 전역 구문 수정기 인스턴스
syntax_fixer = SyntaxFixer() 