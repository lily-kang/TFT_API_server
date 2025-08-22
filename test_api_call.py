import requests
import json

# 테스트 데이터
test_request = {
    "request_id": "test-001",
    "text": "여름휴가 때 가족과 함께 바다에 갔습니다. 파도 소리를 들으며 모래사장을 걸었습니다. 아이들은 모래성을 만들고 놀았습니다. 저녁에는 해변에서 바비큐를 했습니다.",
    "master": {
        "AVG_SENTENCE_LENGTH": 10.0,
        "All_Embedded_Clauses_Ratio": 0.3,
        "CEFR_NVJD_A1A2_lemma_ratio": 0.6
    },
    "referential_clauses": ""
}

# API 호출
try:
    print("=== API 호출 시작 ===")
    response = requests.post(
        "http://localhost:8510/syntax-fix",
        json=test_request,
        timeout=60
    )
    
    print(f"응답 상태: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"전체 성공: {result.get('overall_success')}")
        print(f"원본 텍스트: {result.get('original_text')}")
        print(f"최종 텍스트: {result.get('final_text')}")
        print(f"후보 생성 수: {result.get('candidates_generated')}")
        print(f"후보 통과 수: {result.get('candidates_passed')}")
        
        # 단계별 결과
        print("\n=== 단계별 결과 ===")
        for step in result.get('step_results', []):
            print(f"- {step['step_name']}: {'성공' if step['success'] else '실패'}")
            if step.get('details'):
                print(f"  세부사항: {step['details']}")
        
        # 지표 비교
        print("\n=== 지표 비교 ===")
        original = result.get('original_metrics', {})
        final = result.get('final_metrics', {})
        
        for key in original.keys():
            print(f"{key}:")
            print(f"  원본: {original[key]:.3f}")
            print(f"  최종: {final[key]:.3f}")
            
    else:
        print(f"오류: {response.text}")
        
except Exception as e:
    print(f"요청 실패: {str(e)}") 