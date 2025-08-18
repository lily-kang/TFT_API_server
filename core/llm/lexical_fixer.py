from typing import List, Tuple
from core.llm.client import llm_client
from core.llm.selector import CandidateSelector
from config.prompts import LEXICAL_FIXING_PROMPT
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
            prompt = self._prepare_prompt(text, master, tolerance_ratio)
            
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
    
    def _prepare_prompt(
        self,
        text: str,
        master: MasterMetrics,
        tolerance_ratio: ToleranceRatio
    ) -> str:
        """어휘 수정 프롬프트 준비"""
        
        # 허용 범위 계산
        lexical_tolerance = master.CEFR_NVJD_A1A2_lemma_ratio * tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio
        lexical_min = master.CEFR_NVJD_A1A2_lemma_ratio - lexical_tolerance
        lexical_max = master.CEFR_NVJD_A1A2_lemma_ratio + lexical_tolerance
        
        return LEXICAL_FIXING_PROMPT.format(
            original_text=text,
            target_lexical_ratio=master.CEFR_NVJD_A1A2_lemma_ratio,
            min_lexical=lexical_min,
            max_lexical=lexical_max
        )


# 전역 어휘 수정기 인스턴스
lexical_fixer = LexicalFixer() 