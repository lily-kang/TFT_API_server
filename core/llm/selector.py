from typing import List
from core.llm.client import llm_client
from config.prompts import CANDIDATE_SELECTION_PROMPT
from utils.exceptions import LLMAPIError
from utils.logging import logger


class CandidateSelector:
    """후보 텍스트 중 최적 선택 클래스"""
    
    async def select_best(self, candidates: List[str]) -> str:
        """
        후보 텍스트들 중에서 최적의 텍스트를 선택합니다.
        
        Args:
            candidates: 후보 텍스트 리스트
            
        Returns:
            선택된 최적 텍스트
            
        Raises:
            LLMAPIError: 선택 실패 시
        """
        try:
            if not candidates:
                raise LLMAPIError("선택할 후보가 없습니다")
            
            if len(candidates) == 1:
                return candidates[0]
            
            # 최대 3개까지만 처리
            candidates = candidates[:3]
            
            # 후보가 부족한 경우 첫 번째 후보로 채우기
            while len(candidates) < 3:
                candidates.append(candidates[0])
            
            # 선택 프롬프트 준비
            prompt = CANDIDATE_SELECTION_PROMPT.format(
                candidate_1=candidates[0],
                candidate_2=candidates[1],
                candidate_3=candidates[2]
            )
            
            # LLM으로 선택
            selected_index = await llm_client.select_best_candidate(prompt)
            
            # 1-based 인덱스를 0-based로 변환
            selected_text = candidates[selected_index - 1]
            
            logger.info(f"후보 선택 완료: {selected_index}번 후보 선택")
            return selected_text
            
        except Exception as e:
            logger.error(f"후보 선택 실패: {str(e)}")
            # 실패 시 첫 번째 후보 반환
            if candidates:
                logger.warning("선택 실패로 첫 번째 후보 반환")
                return candidates[0]
            else:
                raise LLMAPIError(f"후보 선택 중 오류 발생: {str(e)}")


# 전역 선택기 인스턴스
candidate_selector = CandidateSelector() 