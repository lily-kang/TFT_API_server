"""
calculate_modification_count 함수 계산 디버깅
"""

# 테스트 케이스: 이전 API 호출에서 사용한 데이터
text = "여름휴가 때 가족과 함께 바다에 갔습니다. 파도 소리를 들으며 모래사장을 걸었습니다. 아이들은 모래성을 만들고 놀았습니다. 저녁에는 해변에서 바비큐를 했습니다."

# Master 설정
master_avg_sentence_length = 10.0
master_clause_ratio = 0.3

# Tolerance 설정 (설정 파일에서)
tolerance_abs_length = 1.97
tolerance_ratio_clause = 0.202

# 목표 범위 계산
target_min_length = master_avg_sentence_length - tolerance_abs_length  # 10.0 - 1.97 = 8.03
target_max_length = master_avg_sentence_length + tolerance_abs_length  # 10.0 + 1.97 = 11.97

clause_tolerance = master_clause_ratio * tolerance_ratio_clause  # 0.3 * 0.202 = 0.0606
target_min_clause = master_clause_ratio - clause_tolerance  # 0.3 - 0.0606 = 0.2394
target_max_clause = master_clause_ratio + clause_tolerance  # 0.3 + 0.0606 = 0.3606

print("=== 목표 범위 ===")
print(f"평균 문장 길이: {target_min_length:.3f} ~ {target_max_length:.3f}")
print(f"복문 비율: {target_min_clause:.3f} ~ {target_max_clause:.3f}")

# 예상 분석 결과 (4문장, 어절 수 추정)
sentence_count = 4
estimated_lexical_tokens = 20  # 추정값

# 복문 정보 (추정)
adverbial_clause_sentences = 0
coordinate_clause_sentences = 0  
nominal_clause_sentences = 0
relative_clause_sentences = 0
total_clause_sentences = 0

print(f"\n=== 분석 데이터 ===")
print(f"문장 수: {sentence_count}")
print(f"어휘 토큰 수: {estimated_lexical_tokens}")
print(f"복문 문장 수: {total_clause_sentences}")

# 현재 지표 계산
current_avg_length = estimated_lexical_tokens / sentence_count  # 20 / 4 = 5.0
current_clause_ratio = total_clause_sentences / sentence_count  # 0 / 4 = 0.0

print(f"\n=== 현재 지표 ===")
print(f"현재 평균 문장 길이: {current_avg_length:.3f}")
print(f"현재 복문 비율: {current_clause_ratio:.3f}")

# 문제 지표 결정
print(f"\n=== 문제 지표 결정 ===")
length_pass = target_min_length <= current_avg_length <= target_max_length
clause_pass = target_min_clause <= current_clause_ratio <= target_max_clause

print(f"평균 문장 길이 통과: {length_pass} ({current_avg_length:.3f} in [{target_min_length:.3f}, {target_max_length:.3f}])")
print(f"복문 비율 통과: {clause_pass} ({current_clause_ratio:.3f} in [{target_min_clause:.3f}, {target_max_clause:.3f}])")

# 문제 지표 (우선순위: 복문 비율 > 평균 문장 길이)
if not clause_pass:
    problematic_metric = "all_embedded_clauses_ratio"
    current_value = current_clause_ratio
    target_min = target_min_clause
    target_max = target_max_clause
elif not length_pass:
    problematic_metric = "avg_sentence_length"
    current_value = current_avg_length
    target_min = target_min_length
    target_max = target_max_length
else:
    problematic_metric = None

print(f"문제 지표: {problematic_metric}")

if problematic_metric:
    print(f"\n=== 수정 문장 수 계산 ===")
    print(f"문제 지표: {problematic_metric}")
    print(f"현재 값: {current_value:.3f}")
    print(f"목표 범위: [{target_min:.3f}, {target_max:.3f}]")
    
    if 'length' in problematic_metric.lower():
        print("▶ 평균 문장 길이 계산")
        if current_value > target_max:
            print(f"  현재값({current_value:.3f}) > 목표최대값({target_max:.3f}) → 문장을 줄여야 함")
            upper_bound = target_max
            calc = (estimated_lexical_tokens / upper_bound) - sentence_count + 0.5
            num_modifications = max(1, round(calc))
            print(f"  계산: round(({estimated_lexical_tokens} / {upper_bound:.3f}) - {sentence_count} + 0.5) = round({calc:.3f}) = {round(calc)}")
        else:
            print(f"  현재값({current_value:.3f}) < 목표최소값({target_min:.3f}) → 문장을 늘려야 함")
            lower_bound = target_min
            calc = sentence_count - round(estimated_lexical_tokens / lower_bound)
            num_modifications = max(1, calc)
            print(f"  계산: {sentence_count} - round({estimated_lexical_tokens} / {lower_bound:.3f}) = {sentence_count} - {round(estimated_lexical_tokens / lower_bound)} = {calc}")
            
    elif 'clause' in problematic_metric.lower() or 'embedded' in problematic_metric.lower():
        print("▶ 복문 비율 계산")
        if current_value > target_max:
            print(f"  현재값({current_value:.3f}) > 목표최대값({target_max:.3f}) → 복문을 줄여야 함")
            target_ratio_upper = target_max
            calc = (total_clause_sentences - (target_ratio_upper * sentence_count)) / (1 + target_ratio_upper) + 0.5
            num_modifications = max(1, round(calc))
            print(f"  계산: round(({total_clause_sentences} - ({target_ratio_upper:.3f} * {sentence_count})) / (1 + {target_ratio_upper:.3f}) + 0.5)")
            print(f"        = round(({total_clause_sentences} - {target_ratio_upper * sentence_count:.3f}) / {1 + target_ratio_upper:.3f} + 0.5)")
            print(f"        = round({calc:.3f}) = {round(calc)}")
        else:
            print(f"  현재값({current_value:.3f}) < 목표최소값({target_min:.3f}) → 복문을 늘려야 함")
            target_ratio_lower = target_min
            calc = ((target_ratio_lower * sentence_count) - total_clause_sentences) / (1 + target_ratio_lower) + 0.5
            num_modifications = max(1, round(calc))
            print(f"  계산: round((({target_ratio_lower:.3f} * {sentence_count}) - {total_clause_sentences}) / (1 + {target_ratio_lower:.3f}) + 0.5)")
            print(f"        = round(({target_ratio_lower * sentence_count:.3f} - {total_clause_sentences}) / {1 + target_ratio_lower:.3f} + 0.5)")
            print(f"        = round({calc:.3f}) = {round(calc)}")
    
    print(f"\n최종 수정 문장 수: {num_modifications}개")
    print(f"예상: 3개, 실제: {num_modifications}개 → {'✅ 일치' if num_modifications == 3 else '❌ 불일치'}") 