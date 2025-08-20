"""
sample_test_data.json의 실제 데이터로 분석기 API 테스트
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

async def test_sample_data():
    """샘플 데이터로 실제 분석기 테스트"""
    
    print("🧪 sample_test_data.json 실제 분석기 테스트 시작")
    print("="*80)
    
    # 샘플 데이터 로드
    sample_input = load_sample_data()
    if not sample_input:
        return
    
    # 환경 변수 설정
    os.environ['OPENAI_API_KEY'] = 'test-key'
    os.environ['DEBUG'] = 'True'
    
    try:
        from core.analyzer import analyzer
        from core.metrics import metrics_extractor
        from core.judge import judge
        from models.request import MasterMetrics, ToleranceAbs, ToleranceRatio
        
        print("✅ 모듈 import 성공")
        
        # 테스트할 텍스트들
        test_texts = {
            "generated_passage": sample_input["generated_passage"]
        }
        
        # 마스터 지표와 허용 오차
        master = MasterMetrics(**sample_input["master"])
        tolerance_abs = ToleranceAbs(**sample_input["tolerance_abs"])
        tolerance_ratio = ToleranceRatio(**sample_input["tolerance_ratio"])
        
        print(f"\n🎯 마스터 지표:")
        print(f"   - 평균 문장 길이: {master.AVG_SENTENCE_LENGTH}")
        print(f"   - 내포절 비율: {master.All_Embedded_Clauses_Ratio}")
        print(f"   - A1A2 어휘 비율: {master.CEFR_NVJD_A1A2_lemma_ratio}")
        
        print(f"\n📏 허용 오차:")
        print(f"   - 절대값 오차 (문장길이): ±{tolerance_abs.AVG_SENTENCE_LENGTH}")
        print(f"   - 비율 오차 (내포절): ±{tolerance_ratio.All_Embedded_Clauses_Ratio}")
        print(f"   - 비율 오차 (A1A2): ±{tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio}")
        
        for text_name, text_content in test_texts.items():
            print(f"\n{'='*80}")
            print(f"📝 {text_name.upper()} 분석 시작")
            print(f"{'='*80}")
            
            # 텍스트 미리보기
            preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
            print(f"📖 텍스트 미리보기:\n{preview}")
            
            print(f"\n🌐 실제 분석기 API 호출 중...")
            
            start_time = time.time()
            
            try:
                # 실제 분석기 호출
                result = await analyzer.analyze(text_content, include_syntax=True)
                
                end_time = time.time()
                duration = end_time - start_time
                
                print(f"✅ 분석 완료! (소요 시간: {duration:.2f}초)")
                
                # 지표 추출 (상세 로깅 포함)
                metrics = metrics_extractor.extract(result)
                
                # 지표 평가
                evaluation = judge.evaluate(metrics, master, tolerance_abs, tolerance_ratio)
                
                print(f"\n🎯 {text_name} 분석 결과:")
                print(f"   📏 평균 문장 길이: {metrics.AVG_SENTENCE_LENGTH:.3f} (목표: {master.AVG_SENTENCE_LENGTH})")
                print(f"   🔗 내포절 비율: {metrics.All_Embedded_Clauses_Ratio:.3f} (목표: {master.All_Embedded_Clauses_Ratio})")
                print(f"   📚 A1A2 어휘 비율: {metrics.CEFR_NVJD_A1A2_lemma_ratio:.3f} (목표: {master.CEFR_NVJD_A1A2_lemma_ratio})")
                
                print(f"\n✅ 평가 결과:")
                print(f"   🔧 구문 통과: {evaluation.syntax_pass}")
                print(f"   📖 어휘 통과: {evaluation.lexical_pass}")
                
                # 상세 평가 결과
                if hasattr(evaluation, 'details') and evaluation.details:
                    print(f"\n📊 상세 평가:")
                    for metric_name, detail in evaluation.details.items():
                        if metric_name not in ["syntax_pass", "lexical_pass"]:
                            current_value = getattr(metrics, metric_name, None)
                            if current_value is not None:
                                min_val = detail.get("min_value", 0)
                                max_val = detail.get("max_value", 0)
                                is_pass = detail.get("is_pass", False)
                                status = "Pass" if is_pass else "Fail"
                                print(f"     {metric_name}: {current_value:.3f} vs [{min_val:.3f} ~ {max_val:.3f}] → {status}")
                
            except Exception as e:
                end_time = time.time()
                duration = end_time - start_time
                print(f"❌ {text_name} 분석 실패 (소요 시간: {duration:.2f}초)")
                print(f"   오류: {str(e)}")
                
        print(f"\n{'='*80}")
        print("🏁 모든 테스트 완료")
        print(f"{'='*80}")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sample_data()) 