import requests
import asyncio
import aiohttp
from typing import Dict, Any
from config.settings import settings
from models.internal import AnalyzerRequest
from utils.exceptions import AnalyzerAPIError


class TextAnalyzer:
    """외부 지문 분석기 API 클라이언트"""
    
    def __init__(self):
        self.api_url = settings.external_analyzer_api_url
        self.timeout = settings.pipeline_timeout
    
    async def analyze(self, text: str, include_syntax: bool = True, llm_model: str = "gpt-4.1") -> Dict[str, Any]:
        """
        텍스트를 외부 분석기 API로 전송하여 분석 결과를 받아옵니다.
        
        Args:
            text: 분석할 텍스트
            include_syntax: 구문 분석 포함 여부
            
        Returns:
            분석 결과 딕셔너리
            
        Raises:
            AnalyzerAPIError: API 호출 실패 시
        """
        request_data = AnalyzerRequest(
            text=text,
            auto_sentence_split=True,
            include_syntax_analysis=include_syntax
        )
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    self.api_url,
                    json={"text": request_data.text, 
                          "auto_sentence_split": request_data.auto_sentence_split,
                          "include_syntax_analysis": request_data.include_syntax_analysis}
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise AnalyzerAPIError(f"API 호출 실패: {response.status} - {error_text}")
                    
                    result = await response.json()
                    return result
                    
        except aiohttp.ClientError as e:
            raise AnalyzerAPIError(f"네트워크 오류: {str(e)}")
        except asyncio.TimeoutError:
            raise AnalyzerAPIError(f"API 호출 타임아웃 ({self.timeout}초)")
        except Exception as e:
            raise AnalyzerAPIError(f"예상치 못한 오류: {str(e)}")
    
    def analyze_sync(self, text: str, include_syntax: bool = True) -> Dict[str, Any]:
        """
        동기식 분석 (기존 main.py 호환용)
        
        Args:
            text: 분석할 텍스트
            include_syntax: 구문 분석 포함 여부
            
        Returns:
            분석 결과 딕셔너리
            
        Raises:
            AnalyzerAPIError: API 호출 실패 시
        """
        try:
            response = requests.post(
                self.api_url,
                json={"text": text},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise AnalyzerAPIError(f"외부 지문 분석 API 호출 실패: {e}")
        except Exception as e:
            raise AnalyzerAPIError(f"서버 오류 발생: {e}")


# 전역 분석기 인스턴스
analyzer = TextAnalyzer() 