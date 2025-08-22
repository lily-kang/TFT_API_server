import openai
import asyncio
from typing import List, Optional
from config.settings import settings
from utils.exceptions import LLMAPIError
from utils.logging import logger


class LLMClient:
    """OpenAI LLM API 클라이언트"""
    
    def __init__(self):
        self.model = settings.openai_model
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization으로 OpenAI 클라이언트 생성"""
        if self._client is None:
            try:
                self._client = openai.OpenAI(api_key=settings.openai_api_key)
                logger.info("OpenAI 클라이언트 초기화 성공")
            except Exception as e:
                logger.error(f"OpenAI 클라이언트 초기화 실패: {e}")
                self._client = None
        return self._client
    
    async def generate_text(self, prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> str:
        """
        단일 텍스트 생성
        
        Args:
            prompt: 생성 프롬프트
            temperature: 생성 온도 (0.0~1.0)
            max_tokens: 최대 토큰 수
            
        Returns:
            생성된 텍스트
            
        Raises:
            LLMAPIError: LLM API 호출 실패 시
        """
        try:
            if not self.client:
                raise LLMAPIError("OpenAI 클라이언트가 초기화되지 않았습니다")
            
            # 동기 호출 사용 (openai 라이브러리의 최신 버전에서는 동기 호출이 기본)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            generated_text = response.choices[0].message.content.strip()
            logger.info(f"텍스트 생성 성공 (temp={temperature}): {len(generated_text)} 글자")
            return generated_text
            
        except Exception as e:
            logger.error(f"텍스트 생성 실패 (temp={temperature}): {str(e)}")
            raise LLMAPIError(f"텍스트 생성 실패: {str(e)}")
    
    async def generate_multiple(self, prompt: str, temperatures: List[float]) -> List[str]:
        """
        여러 temperature로 텍스트 생성 (호환성 유지용)
        
        Args:
            prompt: 생성 프롬프트
            temperatures: temperature 리스트
            
        Returns:
            생성된 텍스트 리스트
        """
        results = []
        for temp in temperatures:
            try:
                text = await self.generate_text(prompt, temperature=temp)
                results.append(text)
            except LLMAPIError as e:
                logger.warning(f"Temperature {temp}에서 생성 실패: {str(e)}")
                results.append(f"[생성 실패: {str(e)}]")
        return results
    
    async def generate_multiple_per_temperature(
        self, 
        prompt: str, 
        temperatures: List[float], 
        candidates_per_temp: int = 2
    ) -> List[str]:
        """
        각 temperature별로 여러 개의 후보 생성 (병렬 처리)
        
        Args:
            prompt: 생성 프롬프트
            temperatures: temperature 리스트
            candidates_per_temp: 각 temperature별 생성할 후보 수
            
        Returns:
            생성된 텍스트 리스트 (총 len(temperatures) × candidates_per_temp 개)
        """
        # 모든 호출을 병렬로 처리하기 위한 태스크 리스트 생성
        tasks = []
        task_info = []  # 로깅용 정보
        
        for temp in temperatures:
            for i in range(candidates_per_temp):
                print(f"temp: {temp}")
                task = self.generate_text(prompt, temperature=temp)
                tasks.append(task)
                task_info.append((temp, i + 1, candidates_per_temp))
        
        total_tasks = len(tasks)
        logger.info(f"총 {total_tasks}개 후보를 병렬로 생성 시작...")
        
        # 병렬 실행
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 처리 및 로깅
            final_results = []
            for i, (result, (temp, candidate_num, total_per_temp)) in enumerate(zip(results, task_info)):
                if isinstance(result, Exception):
                    logger.warning(f"  후보 생성 실패 (temp={temp}, {candidate_num}/{total_per_temp}): {str(result)}")
                    final_results.append(f"[생성 실패: {str(result)}]")
                else:
                    logger.info(f"  후보 {i+1}: 생성 완료 (temp={temp}, {candidate_num}/{total_per_temp})")
                    final_results.append(result)
            
            logger.info(f"병렬 생성 완료: 총 {len(final_results)}개 후보")
            return final_results
            
        except Exception as e:
            logger.error(f"병렬 생성 중 예기치 못한 오류: {str(e)}")
            # 폴백: 순차 처리
            logger.info("폴백: 순차 처리로 재시도...")
            return await self._generate_sequential_fallback(prompt, temperatures, candidates_per_temp)
    
    async def _generate_sequential_fallback(
        self, 
        prompt: str, 
        temperatures: List[float], 
        candidates_per_temp: int
    ) -> List[str]:
        """병렬 처리 실패 시 순차 처리 폴백"""
        results = []
        
        for temp in temperatures:
            logger.info(f"Temperature {temp}로 {candidates_per_temp}개 후보 생성 중... (순차 처리)")
            
            for i in range(candidates_per_temp):
                try:
                    text = await self.generate_text(prompt, temperature=temp)
                    results.append(text)
                    logger.info(f"  후보 {len(results)}: 생성 완료 (temp={temp}, {i+1}/{candidates_per_temp})")
                except LLMAPIError as e:
                    logger.warning(f"  후보 생성 실패 (temp={temp}, {i+1}/{candidates_per_temp}): {str(e)}")
                    results.append(f"[생성 실패: {str(e)}]")
        
        logger.info(f"순차 처리 완료: 총 {len(results)}개 후보")
        return results
    
    async def select_best_candidate(self, selection_prompt: str, temperature: float = 0.1) -> int:
        """
        후보 중 최적 선택
        
        Args:
            selection_prompt: 선택 프롬프트
            temperature: 선택용 온도 (낮게 설정)
            
        Returns:
            선택된 후보 번호 (1부터 시작)
            
        Raises:
            LLMAPIError: LLM API 호출 실패 시
        """
        try:
            response_text = await self.generate_text(selection_prompt, temperature)
            selection_number = self._extract_selection_number(response_text)
            
            logger.info(f"후보 선택 완료: {selection_number}번")
            return selection_number
            
        except Exception as e:
            logger.error(f"후보 선택 실패: {str(e)}")
            raise LLMAPIError(f"후보 선택 실패: {str(e)}")
    
    def _extract_selection_number(self, response: str) -> int:
        """응답에서 선택 번호 추출"""
        try:
            # 숫자 추출 로직
            import re
            numbers = re.findall(r'\d+', response)
            if numbers:
                return int(numbers[0])
            else:
                logger.warning(f"응답에서 숫자를 찾을 수 없음: {response}")
                return 1  # 기본값
        except Exception as e:
            logger.warning(f"선택 번호 추출 실패: {str(e)}")
            return 1  # 기본값


# 전역 LLM 클라이언트 인스턴스
llm_client = LLMClient() 