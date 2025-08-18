import openai
from typing import List, Optional
from config.settings import settings
from utils.exceptions import LLMAPIError
from utils.logging import logger


class LLMClient:
    """OpenAI API 클라이언트"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        텍스트 생성 요청
        
        Args:
            prompt: 입력 프롬프트
            temperature: 생성 다양성 (0.0-1.0)
            max_tokens: 최대 토큰 수
            
        Returns:
            생성된 텍스트
            
        Raises:
            LLMAPIError: API 호출 실패 시
        """
        try:
            response = await self.client.chat.completions.acreate(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            result = response.choices[0].message.content.strip()
            logger.info(f"LLM 텍스트 생성 완료 (temperature={temperature})")
            return result
            
        except Exception as e:
            logger.error(f"LLM API 호출 실패: {str(e)}")
            raise LLMAPIError(f"LLM API 호출 중 오류 발생: {str(e)}")
    
    async def generate_multiple(
        self,
        prompt: str,
        temperatures: List[float]
    ) -> List[str]:
        """
        여러 temperature로 텍스트 생성
        
        Args:
            prompt: 입력 프롬프트
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
    
    async def select_best_candidate(
        self,
        selection_prompt: str,
        temperature: float = 0.1
    ) -> int:
        """
        후보 중 최적 선택
        
        Args:
            selection_prompt: 선택 프롬프트
            temperature: 낮은 temperature로 일관된 선택
            
        Returns:
            선택된 후보 인덱스 (1-based)
            
        Raises:
            LLMAPIError: 선택 실패 시
        """
        try:
            response = await self.generate_text(selection_prompt, temperature=temperature)
            
            # 응답에서 숫자 추출
            selection = self._extract_selection_number(response)
            logger.info(f"LLM 후보 선택 완료: {selection}")
            return selection
            
        except Exception as e:
            logger.error(f"후보 선택 실패: {str(e)}")
            raise LLMAPIError(f"후보 선택 중 오류 발생: {str(e)}")
    
    def _extract_selection_number(self, response: str) -> int:
        """응답에서 선택 번호 추출"""
        import re
        
        # 숫자 패턴 찾기
        numbers = re.findall(r'\b[123]\b', response)
        
        if numbers:
            return int(numbers[0])
        else:
            # 기본값으로 1 반환
            logger.warning(f"선택 번호를 찾을 수 없어 기본값 1 반환. 응답: {response}")
            return 1


# 전역 LLM 클라이언트 인스턴스
llm_client = LLMClient() 