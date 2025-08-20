#!/usr/bin/env python3
"""
프롬프트 구성 테스트 스크립트
전체 파이프라인을 돌리지 않고도 프롬프트가 올바르게 구성되는지 확인할 수 있습니다.
"""

import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.llm.prompt_builder import prompt_builder
from models.request import MasterMetrics, ToleranceAbs, ToleranceRatio


def test_syntax_prompt():
    """구문 수정 프롬프트 테스트"""
    print("=" * 80)
    print("구문 수정 프롬프트 테스트")
    print("=" * 80)
    
    # 테스트 데이터
    test_text = """
    The cat sat on the mat. It was a sunny day. The bird sang in the tree. 
    The children played in the park. They were very happy. The dog ran around.
    """
    
    # 마스터 지표 (예시 값)
    master = MasterMetrics(
        AVG_SENTENCE_LENGTH=12.5,
        All_Embedded_Clauses_Ratio=0.4,
        CEFR_NVJD_A1A2_lemma_ratio=0.6,
        content_lemma_cefr_b1b2c1c2_ratio=0.3
    )
    
    # 허용 오차
    tolerance_abs = ToleranceAbs(
        AVG_SENTENCE_LENGTH=2.0,
        All_Embedded_Clauses_Ratio=0.1
    )
    
    tolerance_ratio = ToleranceRatio(
        All_Embedded_Clauses_Ratio=0.25,
        CEFR_NVJD_A1A2_lemma_ratio=0.2
    )
    
    # 현재 지표 (문제가 있는 상황 시뮬레이션)
    current_metrics = {
        'avg_sentence_length': 8.2,  # 목표보다 낮음
        'embedded_clauses_ratio': 0.2  # 목표보다 낮음
    }
    
    # 문제 지표 결정
    problematic_metric = prompt_builder.determine_problematic_metric(
        current_metrics, master, tolerance_abs, tolerance_ratio
    )
    
    print(f"문제 지표: {problematic_metric}")
    
    if problematic_metric:
        # 수정 문장 수 계산
        num_modifications = prompt_builder.calculate_modification_count(
            test_text, problematic_metric, 
            current_metrics.get('avg_sentence_length', 0),
            master.AVG_SENTENCE_LENGTH - tolerance_abs.AVG_SENTENCE_LENGTH,
            master.AVG_SENTENCE_LENGTH + tolerance_abs.AVG_SENTENCE_LENGTH
        )
        
        # 참조용 절 정보
        referential_clauses = """
        Noun Clauses: that he was tired, what she said, whether they would come
        Relative Clauses: who helped me, which was interesting, whose brother is famous
        Adverbial Clauses: because it was raining, when the sun set, although he tried
        Coordinate Clauses: and he left early, but she stayed, or we could wait
        """
        
        # 프롬프트 생성
        prompt = prompt_builder.build_syntax_prompt(
            test_text, master, tolerance_abs, tolerance_ratio,
            current_metrics, problematic_metric, num_modifications, referential_clauses
        )
        
        print("\n" + "=" * 80)
        print("생성된 프롬프트:")
        print("=" * 80)
        print(prompt)
        print("=" * 80)
        
        # 프롬프트 길이 및 주요 변수 확인
        print(f"\n프롬프트 길이: {len(prompt)} 글자")
        print(f"변수 치환 확인:")
        print(f"- 텍스트 포함: {'{var_Generated_Passage}' not in prompt}")
        print(f"- 문제 지표 포함: {'{var_problematic_metric}' not in prompt}")
        print(f"- 수정 수 포함: {'{var_num_modifications}' not in prompt}")
        print(f"- 현재값 포함: {'{var_current_value_avg_sentence_length}' not in prompt}")
        print(f"- 목표범위 포함: {'{var_target_range_avg_sentence_length}' not in prompt}")
        print(f"- 참조절 포함: {'{var_referential_clauses}' not in prompt}")
        
    else:
        print("문제가 있는 지표가 없습니다.")


def test_lexical_prompt():
    """어휘 수정 프롬프트 테스트"""
    print("\n" + "=" * 80)
    print("어휘 수정 프롬프트 테스트")
    print("=" * 80)
    
    test_text = "The sophisticated individual demonstrated exceptional proficiency in the complex methodology."
    
    master = MasterMetrics(
        AVG_SENTENCE_LENGTH=12.5,
        All_Embedded_Clauses_Ratio=0.4,
        CEFR_NVJD_A1A2_lemma_ratio=0.6,
        content_lemma_cefr_b1b2c1c2_ratio=0.3
    )
    
    tolerance_ratio = ToleranceRatio(
        All_Embedded_Clauses_Ratio=0.25,
        CEFR_NVJD_A1A2_lemma_ratio=0.2
    )
    
    current_metrics = {
        'cefr_a1a2_lemma_ratio': 0.3  # 목표보다 낮음
    }
    
    prompt = prompt_builder.build_lexical_prompt(
        test_text, master, tolerance_ratio, current_metrics
    )
    
    print("\n생성된 프롬프트:")
    print("=" * 80)
    print(prompt)
    print("=" * 80)


def test_selection_prompt():
    """후보 선택 프롬프트 테스트"""
    print("\n" + "=" * 80)
    print("후보 선택 프롬프트 테스트")
    print("=" * 80)
    
    candidate_1 = "The cat sat on the mat. It was a sunny day."
    candidate_2 = "The cat, which was orange, sat on the mat while the sun shone brightly."
    candidate_3 = "A cat sat on a mat. The day was sunny and warm."
    
    prompt = prompt_builder.build_selection_prompt(candidate_1, candidate_2, candidate_3)
    
    print("\n생성된 프롬프트:")
    print("=" * 80)
    print(prompt)
    print("=" * 80)


def main():
    """메인 테스트 함수"""
    print("프롬프트 구성 테스트 시작...")
    
    try:
        test_syntax_prompt()
        test_lexical_prompt()
        test_selection_prompt()
        
        print("\n" + "=" * 80)
        print("모든 테스트 완료!")
        print("=" * 80)
        
    except Exception as e:
        print(f"테스트 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 