"""
실제 외부 분석기 API를 사용한 테스트
Mock 없이 진짜 분석기 호출
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any
from unittest.mock import patch

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# JSON 파일에서 테스트 데이터 로드
def load_test_data():
    """sample_test_data.json에서 테스트 데이터 로드"""
    try:
        with open('sample_test_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['test_cases'][0]['input'], data['mock_responses']
    except Exception as e:
        print(f"❌ 테스트 데이터 로드 실패: {e}")
        return None, None

# LLM만 Mock (분석기는 실제 호출)
async def mock_llm_generate_multiple(prompt: str, temperatures: list) -> list:
    """Mock LLM 다중 생성 (분석기는 실제로 호출됨)"""
    test_data, mock_responses = load_test_data()
    candidates = mock_responses['llm_candidates']['syntax_fixed']
    
    print(f"\n=== 🤖 LLM 구문 수정 프롬프트 (길이: {len(prompt)} 글자) ===")
    print("(실제 LLM 대신 Mock 사용)")
    
    print(f"\n=== 📝 생성된 후보 ({len(temperatures)}개) ===")
    for i, (candidate, temp) in enumerate(zip(candidates, temperatures)):
        print(f"후보 {i+1} (temp={temp}): {candidate[:100]}...")
    
    return candidates

async def mock_llm_select_best_candidate(selection_prompt: str, temperature: float = 0.1) -> int:
    """Mock LLM 후보 선택"""
    test_data, mock_responses = load_test_data()
    selection = mock_responses['llm_selection']
    
    print(f"\n=== 🎯 LLM 후보 선택 (Mock) ===")
    print(f"선택 결과: {selection}번")
    
    return int(selection)

async def test_with_real_analyzer():
    """실제 외부 분석기를 사용한 테스트"""
    print("🚀 실제 외부 분석기 테스트 시작\n")
    
    # 테스트 데이터 로드
    test_input, mock_responses = load_test_data()
    if not test_input:
        return
    
    # 환경 변수 설정
    os.environ['OPENAI_API_KEY'] = 'test-key-for-mock'
    os.environ['DEBUG'] = 'True'
    
    try:
        print("📦 모듈 import 중...")
        
        # 모델 import
        from models.request import PipelineItem, MasterMetrics, ToleranceAbs, ToleranceRatio
        from core.analyzer import analyzer
        
        print("✅ 모듈 import 성공")
        
        # 간단한 텍스트로 실제 분석기 테스트
        test_text = "Iceland is beautiful. This country has waterfalls and hot springs."
        
        print(f"\n🌐 실제 외부 분석기 호출 중...")
        print(f"- API URL: https://ils.jp.ngrok.io/api/enhanced_analyze")
        print(f"- 테스트 텍스트: {test_text}")
        print("- 응답 대기 중... (수 초 소요)")
        
        import time
        start_time = time.time()
        
        try:
            # 실제 분석기 호출
            result = await analyzer.analyze(test_text, include_syntax=True)
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"\n✅ 실제 분석기 응답 완료! (소요 시간: {duration:.2f}초)")
            print(f"📊 응답 구조:")
            
            # 응답 구조 출력
            if isinstance(result, dict):
                for key in result.keys():
                    if key == 'metrics' and isinstance(result[key], dict):
                        print(f"  - {key}: {{")
                        for metric_key, metric_value in result[key].items():
                            print(f"      {metric_key}: {metric_value}")
                        print("    }")
                    else:
                        value_preview = str(result[key])[:100]
                        print(f"  - {key}: {value_preview}...")
            
            # 지표 추출 테스트
            print(f"\n🔍 지표 추출 테스트:")
            from core.metrics import metrics_extractor
            
            try:
                extracted_metrics = metrics_extractor.extract(result)
                print(f"✅ 지표 추출 성공:")
                print(f"  - 평균 문장 길이: {extracted_metrics.AVG_SENTENCE_LENGTH}")
                print(f"  - 내포절 비율: {extracted_metrics.All_Embedded_Clauses_Ratio}")
                print(f"  - A1A2 어휘 비율: {extracted_metrics.CEFR_NVJD_A1A2_lemma_ratio}")
                
            except Exception as e:
                print(f"❌ 지표 추출 실패: {e}")
                print("💡 core/metrics.py의 extract 함수를 실제 API 응답 구조에 맞게 수정 필요")
                
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            print(f"\n❌ 외부 분석기 호출 실패 (소요 시간: {duration:.2f}초)")
            print(f"오류: {str(e)}")

            
    except ImportError as e:
        print(f"❌ 모듈 import 실패: {e}")
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 70)
    print("🌐 실제 외부 분석기 API 테스트")
    print("=" * 70)
    
    asyncio.run(test_with_real_analyzer()) 