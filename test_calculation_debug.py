import asyncio
import json
from core.services.text_processing_service import text_processing_service
from models.request import SyntaxFixRequest, MasterMetrics

async def test_calculation():
    # 사용자가 제공한 테스트 데이터
    request_data = {
        "request_id": "001",
        "text": "Nilo the turtle lived in the sandy valley of Zephi. The valley was dry, but the wind danced through it every day. Nilo wanted to build a tall wind tower that could catch the breeze and cool his tiny home. But he had one problem—he had no idea how to build anything so high. He climbed a dune and stared at the sky, trying to concentrate. 'If I just think hard enough, maybe an idea will come,' he said to himself. Just then, Lola the mouse scampered over the hill. 'Why do you look so puzzled?' she asked. 'I want to build a tower to catch the wind,' Nilo said. 'But it's too hard.' 'You just need some help,' said Lola. I may be small, but I know how to build things.' Nilo looked unsure. 'This job needs strength, not small paws.' Lola smiled. 'But it also needs clever ideas.' Together, they worked all morning. Nilo lifted the stones while Lola placed them just right. It took a lot of effort, and Nilo's legs began to ache. Still, they didn't stop. By sunset, the tower stood tall, and the wind spun through it. You were right,' Nilo said. 'We make a good team.'",
        "master": {
            "AVG_SENTENCE_LENGTH": 7.87,
            "All_Embedded_Clauses_Ratio": 0.254,
            "CEFR_NVJD_A1A2_lemma_ratio": 0.637
        },
        "referential_clauses": ""
    }
    
    # SyntaxFixRequest 객체 생성
    request = SyntaxFixRequest(**request_data)
    
    print("=" * 60)
    print("🔍 calculate_modification_count 디버깅 테스트")
    print("=" * 60)
    print(f"텍스트 길이: {len(request.text)} 글자")
    print(f"마스터 지표: {request.master}")
    print()
    
    try:
        # 구문 수정 실행
        result = await text_processing_service.fix_syntax_single(request)
        
        print("=" * 60)
        print("📊 결과 요약")
        print("=" * 60)
        print(f"전체 성공: {result.overall_success}")
        print(f"수정 성공: {result.revision_success}")
        print(f"생성된 후보: {result.candidates_generated}")
        print(f"통과한 후보: {result.candidates_passed}")
        print(f"총 처리 시간: {result.total_processing_time:.2f}초")
        
        if result.step_results:
            print("\n📋 단계별 결과:")
            for step in result.step_results:
                print(f"  - {step.step_name}: {'성공' if step.success else '실패'} ({step.processing_time:.2f}초)")
                if step.error_message:
                    print(f"    오류: {step.error_message}")
                if step.details:
                    print(f"    상세: {step.details}")
        
        if result.original_metrics and result.final_metrics:
            print("\n📈 지표 변화:")
            print(f"  원본 - 평균 문장 길이: {result.original_metrics['AVG_SENTENCE_LENGTH']:.3f}")
            print(f"  최종 - 평균 문장 길이: {result.final_metrics['AVG_SENTENCE_LENGTH']:.3f}")
            print(f"  원본 - 내포절 비율: {result.original_metrics['All_Embedded_Clauses_Ratio']:.3f}")
            print(f"  최종 - 내포절 비율: {result.final_metrics['All_Embedded_Clauses_Ratio']:.3f}")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_calculation()) 