"""
실제 GPT API + 외부 분석기로 구문 수정 파이프라인 완전 테스트
Mock 없이 전체 파이프라인 실행
"""

import asyncio
import json
import os
import sys
import time

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def load_sample_data():
    """sample_test_data.json에서 테스트 데이터 로드"""
    try:
        with open('sample_test_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['test_cases'][0]['input']
    except Exception as e:
        print(f"❌ 샘플 데이터 로드 실패: {e}")
        return None

async def test_full_syntax_pipeline():
    """실제 API들로 완전한 구문 수정 파이프라인 테스트"""
    
    print("🚀 완전한 구문 수정 파이프라인 테스트 시작")
    print("=" * 80)
    
    # 샘플 데이터 로드
    sample_input = load_sample_data()
    if not sample_input:
        return
    
    try:
        # 모듈 import (설정도 함께 로드됨)
        from config.settings import settings
        from models.request import MasterMetrics, ToleranceAbs, ToleranceRatio
        from core.analyzer import analyzer
        from core.metrics import metrics_extractor
        from core.judge import judge
        from core.llm.syntax_fixer import syntax_fixer
        
        print("✅ 모든 모듈 import 성공")
        
        # OpenAI API 키 확인
        if not settings.openai_api_key or settings.openai_api_key == "your_openai_api_key_here":
            print("❌ OpenAI API 키가 설정되지 않았습니다!")
            return
        
        print(f"✅ OpenAI API 키 확인 완료 (모델: {settings.openai_model})")
        
        # 테스트 데이터 설정
        test_text = sample_input["generated_passage"]
        master = MasterMetrics(**sample_input["master"])
        tolerance_abs = ToleranceAbs(**sample_input["tolerance_abs"])
        tolerance_ratio = ToleranceRatio(**sample_input["tolerance_ratio"])
        
        print(f"\n📋 테스트 설정:")
        print(f"   🎯 마스터 지표:")
        print(f"      - 평균 문장 길이: {master.AVG_SENTENCE_LENGTH}")
        print(f"      - 내포절 비율: {master.All_Embedded_Clauses_Ratio}")
        print(f"      - A1A2 어휘 비율: {master.CEFR_NVJD_A1A2_lemma_ratio}")
        print(f"   📏 허용 오차:")
        print(f"      - 절대값 오차 (문장길이): ±{tolerance_abs.AVG_SENTENCE_LENGTH}")
        print(f"      - 비율 오차 (내포절): ±{tolerance_ratio.All_Embedded_Clauses_Ratio}")
        print(f"      - 비율 오차 (A1A2): ±{tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio}")
        print(f"   📝 var_num_modifications: 3")
        print(f"   🌡️ Temperature 설정: {settings.llm_temperatures} × 각 {settings.syntax_candidates_per_temperature}개")
        
        # 테스트 텍스트 미리보기
        preview = test_text[:200] + "..." if len(test_text) > 200 else test_text
        print(f"\n📖 지문 텍스트 미리보기:\n{preview}")
        
        print(f"\n" + "=" * 80)
        print("🔄 단계 1: 지문 텍스트 분석")
        print("=" * 80)
        
        start_time = time.time()
        
        # 1단계: 생성문 텍스트 분석
        print("🌐 외부 분석기로 생성문 텍스트 분석 중...")
        original_analysis = await analyzer.analyze(test_text, include_syntax=True)
        original_metrics = metrics_extractor.extract(original_analysis)
        original_evaluation = judge.evaluate(original_metrics, master, tolerance_abs, tolerance_ratio)
        
        analysis_time = time.time() - start_time
        
        print(f"✅ 지문 분석 완료 (소요 시간: {analysis_time:.2f}초)")
        print(f"📊 원본 지표:")
        print(f"   - 평균 문장 길이: {original_metrics.AVG_SENTENCE_LENGTH:.3f}")
        print(f"   - 내포절 비율: {original_metrics.All_Embedded_Clauses_Ratio:.3f}")
        print(f"   - A1A2 어휘 비율: {original_metrics.CEFR_NVJD_A1A2_lemma_ratio:.3f}")
        print(f"📈 원본 평가:")
        print(f"   - 구문 통과: {original_evaluation.syntax_pass}")
        print(f"   - 어휘 통과: {original_evaluation.lexical_pass}")
        
        # 구문 수정이 필요한지 확인
        if original_evaluation.syntax_pass == "PASS":
            print("✅ 생성지문 텍스트가 이미 구문 지표를 통과했습니다!")
            print("🔚 테스트를 종료합니다.")
            return
        
        print(f"\n" + "=" * 80)
        print("🔄 단계 2: 구문 수정 수행")
        print("=" * 80)
        
        # 2단계: 구문 수정 수행
        print("🤖 GPT API로 구문 수정 중...")
        print(f"   - Temperature 설정: {settings.llm_temperatures} × 각 {settings.syntax_candidates_per_temperature}개 = 총 {len(settings.llm_temperatures) * settings.syntax_candidates_per_temperature}개 후보 생성")
        print("   - var_num_modifications: 3")
        
        # current_metrics를 딕셔너리로 변환
        current_metrics_dict = {
            'AVG_SENTENCE_LENGTH': original_metrics.AVG_SENTENCE_LENGTH,
            'All_Embedded_Clauses_Ratio': original_metrics.All_Embedded_Clauses_Ratio,
            'CEFR_NVJD_A1A2_lemma_ratio': original_metrics.CEFR_NVJD_A1A2_lemma_ratio
        }
        
        syntax_start_time = time.time()
        
        try:
            # 구문 수정 실행
            candidates, selected_text, final_metrics, final_evaluation = await syntax_fixer.fix_syntax(
                text=test_text,
                master=master,
                tolerance_abs=tolerance_abs,
                tolerance_ratio=tolerance_ratio,
                current_metrics=current_metrics_dict,
                referential_clauses=""  # 빈 문자열로 설정
            )
            
            syntax_time = time.time() - syntax_start_time
            
            print(f"✅ 구문 수정 완료 (소요 시간: {syntax_time:.2f}초)")
            print(f"📝 생성된 후보 수: {len(candidates)}개")
            print(f"🎯 선택된 텍스트:")
            print(f"   {selected_text[:300]}...")
            
            print(f"\n" + "=" * 80)
            print("🔄 단계 3: 어휘 수정 (필요시)")
            print("=" * 80)
            
            # 3단계: 어휘 수정 (필요시)
            # TODO: 어휘 수정 로직 추가 예정
            print("📚 어휘 수정은 현재 구현 중입니다.")
            
            final_text = selected_text  # 현재는 구문 수정 결과를 최종 결과로 사용
            
            print(f"\n" + "=" * 80)
            print("🎊 최종 결과")
            print("=" * 80)
            
            total_time = time.time() - start_time
            
            # 결과 비교표
            # print(f"📊 지표 비교:")
            # print(f"   지표                    | 원본        | 수정 후     | 목표         | 상태")
            # print(f"   ----------------------- | ----------- | ----------- | ------------ | ----")
            # print(f"   평균 문장 길이          | {original_metrics.AVG_SENTENCE_LENGTH:8.3f}    | {final_metrics.AVG_SENTENCE_LENGTH:8.3f}    | {master.AVG_SENTENCE_LENGTH:8.3f}       | {'✅' if final_evaluation.syntax_pass == 'PASS' else '❌'}")
            # print(f"   내포절 비율             | {original_metrics.All_Embedded_Clauses_Ratio:8.3f}    | {final_metrics.All_Embedded_Clauses_Ratio:8.3f}    | {master.All_Embedded_Clauses_Ratio:8.3f}       | {'✅' if final_evaluation.syntax_pass == 'PASS' else '❌'}")
            # print(f"   A1A2 어휘 비율         | {original_metrics.CEFR_NVJD_A1A2_lemma_ratio:8.3f}    | {final_metrics.CEFR_NVJD_A1A2_lemma_ratio:8.3f}    | {master.CEFR_NVJD_A1A2_lemma_ratio:8.3f}       | {'✅' if final_evaluation.lexical_pass == 'PASS' else '❌'}")
            
            print(f"\n📈 최종 평가:")
            print(f"   🔧 구문 통과: {final_evaluation.syntax_pass}")
            print(f"   📖 어휘 통과: {final_evaluation.lexical_pass}")
            
            print(f"\n⏱️ 소요 시간:")
            print(f"   - 원본 분석: {analysis_time:.2f}초")
            print(f"   - 구문 수정: {syntax_time:.2f}초")
            print(f"   - 전체: {total_time:.2f}초")
            
            print(f"\n📝 최종 텍스트:")
            print(f"   {selected_text}")
            
            # 성공 여부 판단
            if final_evaluation.syntax_pass == "PASS":
                print(f"\n🎉 구문 수정 성공! 목표 지표를 달성했습니다!")
            else:
                print(f"\n⚠️ 구문 수정 미완료. 추가 수정이 필요할 수 있습니다.")
                
        except Exception as e:
            syntax_time = time.time() - syntax_start_time
            print(f"❌ 구문 수정 실패 (소요 시간: {syntax_time:.2f}초)")
            print(f"   오류: {str(e)}")
            
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_syntax_pipeline()) 