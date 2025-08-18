"""LLM 프롬프트 템플릿 관리"""

# 구문 수정 프롬프트 (기존 작성된 것이 있다고 가정)
SYNTAX_FIXING_PROMPT = """
당신은 텍스트의 구문적 복잡도를 조정하는 전문가입니다.

주어진 텍스트를 다음 구문 지표에 맞게 수정해주세요:
- 평균 문장 길이 (AVG_SENTENCE_LENGTH)
- 내포절 비율 (All_Embedded_Clauses_Ratio)

원본 텍스트: {original_text}

목표 지표:
- AVG_SENTENCE_LENGTH: {target_avg_length} (허용 범위: {min_length} ~ {max_length})
- All_Embedded_Clauses_Ratio: {target_clause_ratio} (허용 범위: {min_clause} ~ {max_clause})

수정된 텍스트를 제공해주세요. 원본의 의미와 내용은 최대한 보존하면서 구문적 복잡도만 조정해주세요.
"""

# 어휘 수정 프롬프트 (작성 중이라고 했으므로 기본 템플릿만 제공)
LEXICAL_FIXING_PROMPT = """
당신은 텍스트의 어휘적 난이도를 조정하는 전문가입니다.

주어진 텍스트를 다음 어휘 지표에 맞게 수정해주세요:
- CEFR A1A2 어휘 비율 (CEFR_NVJD_A1A2_lemma_ratio)

원본 텍스트: {original_text}

목표 지표:
- CEFR_NVJD_A1A2_lemma_ratio: {target_lexical_ratio} (허용 범위: {min_lexical} ~ {max_lexical})

수정된 텍스트를 제공해주세요. 원본의 의미와 내용은 최대한 보존하면서 어휘 난이도만 조정해주세요.

참고: 이 프롬프트는 현재 작성 중입니다.
"""

# 최적 지문 선택 프롬프트 (기존 작성된 것이 있다고 가정)
CANDIDATE_SELECTION_PROMPT = """
당신은 여러 텍스트 후보 중에서 최적의 텍스트를 선택하는 전문가입니다.

다음 후보들 중에서 가장 자연스럽고 품질이 높은 텍스트를 선택해주세요:

후보 1: {candidate_1}
후보 2: {candidate_2}
후보 3: {candidate_3}

선택 기준:
1. 자연스러운 문체와 흐름
2. 의미의 명확성
3. 문법적 정확성
4. 전체적인 가독성

선택한 후보의 번호(1, 2, 또는 3)만 응답해주세요.
""" 