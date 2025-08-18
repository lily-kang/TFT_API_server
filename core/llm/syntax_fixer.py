from typing import List, Tuple
from core.llm.client import llm_client
from core.llm.selector import CandidateSelector
from config.prompts import SYNTAX_FIXING_PROMPT
from config.settings import settings
from models.request import MasterMetrics, ToleranceAbs, ToleranceRatio
from models.internal import LLMCandidate, LLMResponse
from utils.exceptions import LLMAPIError
from utils.logging import logger


class SyntaxFixer:
    """구문 수정 클래스"""
    
    def __init__(self):
        self.selector = CandidateSelector()
        self.temperatures = settings.llm_temperatures
    
    async def fix_syntax(
        self,
        text: str,
        master: MasterMetrics,
        tolerance_abs: ToleranceAbs,
        tolerance_ratio: ToleranceRatio,
        n_candidates: int = 3
    ) -> Tuple[List[str], str]:
        """
        구문 수정을 수행합니다.
        
        Args:
            text: 수정할 텍스트
            master: 마스터 지표
            tolerance_abs: 절대값 허용 오차
            tolerance_ratio: 비율 허용 오차
            n_candidates: 생성할 후보 개수
            
        Returns:
            (후보 리스트, 선택된 텍스트) 튜플
            
        Raises:
            LLMAPIError: LLM 호출 실패 시
        """
        try:
            logger.info(f"구문 수정 시작: {len(text)} 글자")
            
            # 프롬프트 준비
            prompt = self._prepare_prompt(text, master, tolerance_abs, tolerance_ratio)
            
            # 여러 temperature로 후보 생성
            temperatures = self.temperatures[:n_candidates]
            candidates = await llm_client.generate_multiple(prompt, temperatures)
            
            # 후보 중 최적 선택
            selected_text = await self.selector.select_best(candidates)
            
            logger.info(f"구문 수정 완료: {n_candidates}개 후보 중 선택")
            return candidates, selected_text
            
        except Exception as e:
            logger.error(f"구문 수정 실패: {str(e)}")
            raise LLMAPIError(f"구문 수정 중 오류 발생: {str(e)}")
    
    def _prepare_prompt(
        self,
        text: str,
        master: MasterMetrics,
        tolerance_abs: ToleranceAbs,
        tolerance_ratio: ToleranceRatio
    ) -> str:
        """구문 수정 프롬프트 준비"""
        
        # 허용 범위 계산
        length_min = master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH
        length_max = master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
        
        clause_tolerance = master.All_Embedded_Clauses_Ratio * tolerance_ratio.All_Embedded_Clauses_Ratio
        clause_min = master.All_Embedded_Clauses_Ratio - clause_tolerance
        clause_max = master.All_Embedded_Clauses_Ratio + clause_tolerance
        
        return SYNTAX_FIXING_PROMPT.format(
            original_text=text,
            target_avg_length=master.AVG_SENTENCE_LENGTH,
            min_length=length_min,
            max_length=length_max,
            target_clause_ratio=master.All_Embedded_Clauses_Ratio,
            min_clause=clause_min,
            max_clause=clause_max
        )


# 전역 구문 수정기 인스턴스
syntax_fixer = SyntaxFixer() 