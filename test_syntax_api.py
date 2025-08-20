"""
구문 수정 API 테스트 스크립트
앱스크립트에서 호출하는 방식과 동일하게 테스트
"""

import asyncio
import json
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_syntax_fix_api():
    """구문 수정 API 테스트"""
    
    print("🧪 구문 수정 API 테스트 시작")
    print("=" * 60)
    
    try:
        # API 모듈 import
        from api.router import fix_syntax
        from models.request import SyntaxFixRequest, MasterMetrics, ToleranceAbs, ToleranceRatio
        
        # 테스트 데이터 준비
        request = SyntaxFixRequest(
            request_id="test_001",
            text="""Iceland is a country full of natural beauty. This unique location has waterfalls, hot springs, and even volcanoes. Some volcanoes are still active, which means they can still erupt with lava. People come from around the world to visit these places.

Iceland also has many glaciers. These rivers of ice form when one layer of snow presses down on another. Over many years, the snow turns into solid ice. The glaciers slowly move across the land, shaping it as they go.

The temperature in Iceland changes with the seasons. Winters can be cold, but summers are cool and mild. The darkness in winter lasts a long time in some parts of the country. In summer, people enjoy long days with lots of sunlight.

People in Iceland are proud of their land. Their towns are small but lively, and they love to explore the outdoors. If you visit Iceland, you might see puffins, whales, or even the northern lights!""",
            master=MasterMetrics(
                AVG_SENTENCE_LENGTH=8.85,
                All_Embedded_Clauses_Ratio=0.176,
                CEFR_NVJD_A1A2_lemma_ratio=0.583
            ),
            tolerance_abs=ToleranceAbs(AVG_SENTENCE_LENGTH=1.97),
            tolerance_ratio=ToleranceRatio(
                All_Embedded_Clauses_Ratio=0.202,
                CEFR_NVJD_A1A2_lemma_ratio=0.104
            ),
            referential_clauses=""  # 기본값 사용
        )
        
        print(f"📝 요청 ID: {request.request_id}")
        print(f"📏 텍스트 길이: {len(request.text)} 글자")
        print(f"🎯 마스터 지표:")
        print(f"   - 평균 문장 길이: {request.master.AVG_SENTENCE_LENGTH}")
        print(f"   - 내포절 비율: {request.master.All_Embedded_Clauses_Ratio}")
        print(f"   - A1A2 어휘 비율: {request.master.CEFR_NVJD_A1A2_lemma_ratio}")
        
        print(f"\n🚀 API 호출 시작...")
        
        # API 호출
        response = await fix_syntax(request)
        
        print(f"\n📊 응답 결과:")
        print(f"   ✅ 성공 여부: {response.success}")
        print(f"   🆔 요청 ID: {response.request_id}")
        print(f"   ⏱️ 처리 시간: {response.processing_time:.2f}초")
        print(f"   🔢 생성된 후보 수: {response.candidates_generated}")
        print(f"   ✅ 통과한 후보 수: {response.candidates_passed}")
        
        if response.success:
            print(f"\n📈 지표 비교:")
            if response.original_metrics and response.fixed_metrics:
                print(f"   구분                  | 원본        | 수정 후")
                print(f"   -------------------- | ----------- | -----------")
                print(f"   평균 문장 길이        | {response.original_metrics['AVG_SENTENCE_LENGTH']:8.3f}    | {response.fixed_metrics['AVG_SENTENCE_LENGTH']:8.3f}")
                print(f"   내포절 비율          | {response.original_metrics['All_Embedded_Clauses_Ratio']:8.3f}    | {response.fixed_metrics['All_Embedded_Clauses_Ratio']:8.3f}")
                print(f"   A1A2 어휘 비율       | {response.original_metrics['CEFR_NVJD_A1A2_lemma_ratio']:8.3f}    | {response.fixed_metrics['CEFR_NVJD_A1A2_lemma_ratio']:8.3f}")
            
            print(f"\n📝 수정된 텍스트:")
            print(f"   {response.fixed_text[:200]}...")
        else:
            print(f"\n❌ 실패:")
            print(f"   오류: {response.error_message}")
        
        # JSON 형태로도 출력 (앱스크립트 참고용)
        print(f"\n🔗 JSON 응답 (앱스크립트 참고):")
        response_dict = response.model_dump()
        print(json.dumps(response_dict, indent=2, ensure_ascii=False))
        
        print(f"\n🎉 API 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_syntax_fix_api()) 