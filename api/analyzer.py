from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.analyzer import analyzer
from utils.logging import logger

router = APIRouter(tags=["analyzer"])


class TextInput(BaseModel):
    """텍스트 분석 요청 모델"""
    text: str
    auto_sentence_split: bool = True
    include_syntax_analysis: bool = True


@router.post(
    "/analyze",
    summary="텍스트 지문 분석 요청",
    response_description="지문 분석 결과"
)
async def analyze_text(data: TextInput):
    """
    제공된 텍스트를 외부 지문 분석기 API로 보내고, 그 결과를 반환합니다.
    """
    try:
        logger.info(f"텍스트 분석 요청: {len(data.text)} 글자")
        
        # 외부 분석기 API 호출
        result = await analyzer.analyze(data.text, data.include_syntax_analysis)
        
        logger.info("텍스트 분석 완료")
        return result
        
    except Exception as e:
        logger.error(f"텍스트 분석 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"텍스트 분석 중 오류가 발생했습니다: {str(e)}"
        ) 