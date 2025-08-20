from typing import List, Tuple, Dict
from core.llm.client import llm_client
from core.llm.selector import CandidateSelector
from core.llm.prompt_builder import prompt_builder
from config.settings import settings
from models.request import MasterMetrics, ToleranceRatio
from utils.exceptions import LLMAPIError
from utils.logging import logger


class LexicalFixer:
    """어휘 수정 클래스"""
    
    def __init__(self):
        self.selector = CandidateSelector()
        self.temperatures = settings.llm_temperatures
    
    async def fix_lexical(
        self,
        text: str,
        master: MasterMetrics,
        tolerance_ratio: ToleranceRatio,
        current_metrics: Dict[str, float],
        n_candidates: int = 3
    ) -> Tuple[List[str], str]:
        """
        어휘 수정을 수행합니다.
        
        Args:
            text: 수정할 텍스트
            master: 마스터 지표
            tolerance_ratio: 비율 허용 오차
            n_candidates: 생성할 후보 개수
            
        Returns:
            (후보 리스트, 선택된 텍스트) 튜플
            
        Raises:
            LLMAPIError: LLM 호출 실패 시
        """
        try:
            logger.info(f"어휘 수정 시작: {len(text)} 글자")
            
            # 프롬프트 준비
            prompt = prompt_builder.build_lexical_prompt(text, master, tolerance_ratio, current_metrics)
            
            # 여러 temperature로 후보 생성
            temperatures = self.temperatures[:n_candidates]
            candidates = await llm_client.generate_multiple(prompt, temperatures)
            
            # 후보 중 최적 선택
            selected_text = await self.selector.select_best(candidates)
            
            logger.info(f"어휘 수정 완료: {n_candidates}개 후보 중 선택")
            return candidates, selected_text
            
        except Exception as e:
            logger.error(f"어휘 수정 실패: {str(e)}")
            raise LLMAPIError(f"어휘 수정 중 오류 발생: {str(e)}")
    



# 전역 어휘 수정기 인스턴스
lexical_fixer = LexicalFixer() 