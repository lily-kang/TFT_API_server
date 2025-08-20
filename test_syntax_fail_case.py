"""
syntax_fail_case 단일 테스트 스크립트
실제 사용자 데이터로 구문 수정 모듈 테스트
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

# Mock 함수들
async def mock_analyzer_analyze(text: str, include_syntax: bool = True) -> Dict[str, Any]:
    """Mock 외부 분석기 - 텍스트에 따라 다른 응답"""
    test_data, mock_responses = load_test_data()
    
    # 원본 텍스트
    if "Iceland is a country full of natural beauty" in text:
        print("📊 원본 텍스트 분석 중...")
        return {"metrics": mock_responses['analyzer_responses']['original_text']['metrics']}
    
    # 후보 1 - 실패 케이스 (문장이 너무 짧음)
    elif "Iceland has natural beauty" in text and "It has waterfalls and hot springs" in text:
        print("📊 후보 1 분석 중... (실패 예정)")
        return {"metrics": {
            "AVG_SENTENCE_LENGTH": 6.5,  # 허용 범위 밖 (너무 짧음)
            "All_Embedded_Clauses_Ratio": 0.15,
            "CEFR_NVJD_A1A2_lemma_ratio": 0.60,
            "AVG_CONTENT_SYLLABLES": 2.0,
            "CL_CEFR_B1B2C1C2_ratio": 0.16,
            "PP_Weighted_Ratio": 1.0
        }}
    
    # 후보 2 - 성공 케이스
    elif "Iceland is beautiful" in text:
        print("📊 후보 2 분석 중... (성공 예정)")
        return {"metrics": mock_responses['analyzer_responses']['improved_text']['metrics']}
    
    # 후보 3 - 성공 케이스
    elif "Iceland is a country with natural beauty" in text:
        print("📊 후보 3 분석 중... (성공 예정)")
        return {"metrics": {
            "AVG_SENTENCE_LENGTH": 9.2,  # 허용 범위 내
            "All_Embedded_Clauses_Ratio": 0.17,
            "CEFR_NVJD_A1A2_lemma_ratio": 0.59,
            "AVG_CONTENT_SYLLABLES": 2.2,
            "CL_CEFR_B1B2C1C2_ratio": 0.19,
            "PP_Weighted_Ratio": 1.3
        }}
    
    # 기본값 (수정된 텍스트)
    else:
        print("📊 수정된 텍스트 분석 중...")
        return {"metrics": mock_responses['analyzer_responses']['improved_text']['metrics']}

async def mock_llm_generate_multiple(prompt: str, temperatures: list) -> list:
    """Mock LLM 다중 생성"""
    test_data, mock_responses = load_test_data()
    candidates = mock_responses['llm_candidates']['syntax_fixed']
    
    print(f"\n=== 🤖 LLM 구문 수정 프롬프트 (길이: {len(prompt)} 글자) ===")
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    
    print(f"\n=== 📝 생성된 후보 ({len(temperatures)}개) ===")
    for i, (candidate, temp) in enumerate(zip(candidates, temperatures)):
        print(f"후보 {i+1} (temp={temp}): {candidate[:100]}...")
    
    return candidates

async def mock_llm_select_best_candidate(selection_prompt: str, temperature: float = 0.1) -> int:
    """Mock LLM 후보 선택"""
    test_data, mock_responses = load_test_data()
    selection = mock_responses['llm_selection']
    
    print(f"\n=== 🎯 LLM 후보 선택 프롬프트 ===")
    print(selection_prompt[:300] + "..." if len(selection_prompt) > 300 else selection_prompt)
    print(f"\n=== ✅ 선택 결과: {selection}번 ===")
    
    return int(selection)

async def test_syntax_fail_case():
    """syntax_fail_case 테스트"""
    print("🚀 syntax_fail_case 테스트 시작\n")
    
    # 테스트 데이터 로드
    test_input, mock_responses = load_test_data()
    if not test_input:
        return
    
    # 환경 변수 설정
    os.environ['OPENAI_API_KEY'] = 'test-key-for-mock'
    os.environ['DEBUG'] = 'True'
    
    # Mock 설정 - 모듈 import 후에 패치
    try:
        print("📦 모듈 import 중...")
        
        # 모델 import
        from models.request import PipelineItem, MasterMetrics, ToleranceAbs, ToleranceRatio
        from core.pipeline import PipelineProcessor
        
        print("✅ 모듈 import 성공")
        
        # Mock 패치 적용
        with patch('core.analyzer.analyzer.analyze', side_effect=mock_analyzer_analyze), \
             patch('core.llm.client.llm_client.generate_multiple', side_effect=mock_llm_generate_multiple), \
             patch('core.llm.client.llm_client.select_best_candidate', side_effect=mock_llm_select_best_candidate):
            
            # 테스트 데이터 생성
            pipeline_item = PipelineItem(
                client_id=test_input['client_id'],
                original_text=test_input['original_text'],
                title=test_input['title'],
                generated_passage=test_input['generated_passage'],
                include_syntax=test_input['include_syntax'],
                master=MasterMetrics(**test_input['master']),
                tolerance_abs=ToleranceAbs(**test_input['tolerance_abs']),
                tolerance_ratio=ToleranceRatio(**test_input['tolerance_ratio']),
                syntax_candidates=test_input['syntax_candidates'],
                lexical_candidates=test_input['lexical_candidates']
            )
            
            print("📝 테스트 데이터 정보:")
            print(f"- Client ID: {test_input['client_id']}")
            print(f"- 텍스트 길이: {len(test_input['generated_passage'])} 글자")
            print(f"- 목표 평균 문장 길이: {test_input['master']['AVG_SENTENCE_LENGTH']} (±{test_input['tolerance_abs']['AVG_SENTENCE_LENGTH']})")
            print(f"- 목표 내포절 비율: {test_input['master']['All_Embedded_Clauses_Ratio']} (±{test_input['tolerance_ratio']['All_Embedded_Clauses_Ratio']*100:.1f}%)")
            print(f"- 목표 A1A2 비율: {test_input['master']['CEFR_NVJD_A1A2_lemma_ratio']} (±{test_input['tolerance_ratio']['CEFR_NVJD_A1A2_lemma_ratio']*100:.1f}%)")
            
            print(f"\n📊 예상 후보 검증 결과:")
            print(f"- 후보 1: 평균 문장 길이 6.5 → ❌ FAIL (허용: 6.88-10.82)")
            print(f"- 후보 2: 평균 문장 길이 8.9 → ✅ PASS")
            print(f"- 후보 3: 평균 문장 길이 9.2 → ✅ PASS")
            print(f"- 예상: 2개 후보 통과 → LLM이 선택")
            
            # 파이프라인 실행
            print(f"\n🔄 파이프라인 실행 중...")
            processor = PipelineProcessor()
            result = await processor.run_pipeline(pipeline_item)
            
            # 결과 출력
            print(f"\n📊 테스트 결과:")
            print(f"- Client ID: {result.client_id}")
            print(f"- 최종 상태: {result.status}")
            print(f"- 구문 통과: {result.syntax_pass}")
            print(f"- 어휘 통과: {result.lexical_pass}")
            print(f"- 시도 횟수: 구문={result.attempts.syntax}, 어휘={result.attempts.lexical}")
            
            if result.final_text:
                print(f"\n📝 최종 텍스트 (처음 200자):")
                print(f"{result.final_text[:200]}...")
            
            print(f"\n📈 상세 지표 결과:")
            print(result.detailed_result)
            
            # 처리 과정 추적
            if result.trace:
                print(f"\n🔍 처리 과정 추적:")
                for i, step in enumerate(result.trace):
                    print(f"  {i+1}. {step.step}")
                    if step.metrics:
                        avg_len = step.metrics.get('AVG_SENTENCE_LENGTH', 'N/A')
                        clause_ratio = step.metrics.get('All_Embedded_Clauses_Ratio', 'N/A')
                        lexical_ratio = step.metrics.get('CEFR_NVJD_A1A2_lemma_ratio', 'N/A')
                        print(f"     📏 평균 문장 길이: {avg_len}")
                        print(f"     🔗 내포절 비율: {clause_ratio}")
                        print(f"     📚 A1A2 어휘 비율: {lexical_ratio}")
                    if step.selected:
                        print(f"     ✅ 선택된 텍스트: {step.selected[:80]}...")
            
            # 성공 여부 판단
            if result.status == "final":
                print(f"\n✅ 테스트 성공! 구문 수정이 정상적으로 완료되었습니다.")
                print("🎯 기대한 플로우: analyze → fix_syntax (후보 검증 포함) → reanalyze_after_syntax")
            else:
                print(f"\n❌ 테스트 실패: {result.status}")
                if result.error_message:
                    print(f"   💥 오류 메시지: {result.error_message}")
                    
    except ImportError as e:
        print(f"❌ 모듈 import 실패: {e}")
        print("다음 사항을 확인해주세요:")
        print("1. pip install -r requirements.txt")
        print("2. __init__.py 파일들이 각 디렉토리에 있는지 확인")
        print("3. 현재 작업 디렉토리가 프로젝트 루트인지 확인")
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 syntax_fail_case 단일 테스트 (후보 검증 포함)")
    print("=" * 70)
    
    asyncio.run(test_syntax_fail_case()) 