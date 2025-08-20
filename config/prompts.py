"""LLM 프롬프트 템플릿 관리"""

# 구문 수정 프롬프트 
SYNTAX_FIXING_PROMPT = """
    # Input
    **1. The text to be edited**
    {var_Generated_Passage}

    **2. The problematic metric and the target number of sentence modifications required (*this number assumes the total sentence count remains constant*)**
    - Problematic Metric: {var_problematic_metric}
    - Number of Modifications: {var_num_modifications}

    **3. The current values and target ranges for the key metrics (#1, #4)**
    - average sentence length current value: {var_current_value_avg_sentence_length}
    - average sentence length target range: {var_target_range_avg_sentence_length}
    - embedded clause ratio current value: {var_current_value_embedded_clauses_ratio}
    - embedded clause ratio target range: {var_target_range_embedded_clauses_ratio}

    **4. The complex clauses (noun, adjective, adverbial) and compound clauses (coordinate) to refer to**
    {var_referential_clauses}
    ---
    You are a Text Editor that revises texts to meet specific quantitative metrics. The quantitative metrics we are focusing on are the four listed below.

    **1. Average number of words per sentence (average sentence length)**
    2. Ratio of CEFR A1 + A2 lemmas for nouns, verbs, adjectives, and adverbs (cefr_a1+a2_NJVD_lemma_ratio)
    3. Ratio of CEFR B1+B2+C1+C2 lemmas for content words (content_lemma_cefr_b1+b2+c1+c2_ratio)
    **4. The total number of noun clauses, adjective clauses, adverbial clauses, and coordinate clauses divided by the number of sentences (all_embedded_clauses_ratio)**

    # Role and Editing Principles
    1.  **Surgical, Minimal Edits (This is your MOST IMPORTANT principle)**: Your editing style must be 'surgical'. This means you must preserve the original sentence structure and wording as much as humanly possible, only making the smallest change necessary to affect the target metric.
        - **Surgical Methods**: Your edits must use one of the following surgical methods, depending on the metric you are targeting.
            - **a) Methods for INCREASING Complexity (for all_embedded_clauses_ratio)**: Inserting a new subordinate clause (relative, adverbial, nominal); Connecting two simple sentences with a coordinating conjunction.
            - **b) Methods for DECREASING Complexity (for all_embedded_clauses_ratio)**: Removing a subordinate clause to create a simple sentence; Splitting a compound sentence into two separate simple sentences.
            - **c) Methods for INCREASING Sentence Length (for average sentence length)**: (primary) Combine two short, related simple sentences into one longer sentence; (secondary) Inserting descriptive words or phrases (e.g., adjectives, adverbs, prepositional phrases).
            - **d) Methods for DECREASING Sentence Length (for average sentence length)**: (primary) Split a long simple, complex, or compound sentence into two or more shorter sentences; (secondary) Removing non-essential descriptive words or phrases.
        - **Forbidden Actions**: You are strictly forbidden from rewriting entire sentences for 'style' or 'flow'. Do NOT change the core meaning of a sentence. Do NOT substitute words unnecessarily just because you think they sound better.
    2.  **Precise Metric Targeting Logic**: Your primary objective is to adjust the 'problematic metric' to the **nearest edge** of the provided target range. To achieve this, you **MUST** modify **at least** the number of sentences specified in 'number of modifications needed'. This is a strict and non-negotiable minimum requirement. Based on the metric's current value, apply one of the following rules:
        - **Priority Rule for Conflicting Metrics**: In cases where both average sentence length (#1) and all_embedded_clauses_ratio (#4) are outside their target ranges, you **MUST** prioritize the methods for metric **#4** (all_embedded_clauses_ratio). In this scenario, you will apply the editing rules for #4 and ignore the rules for #1.
        - **Rule 1: If the current value is BELOW the range's minimum:** Your goal is to bring the new value as close as possible to the **MINIMUM** of the target range. To do this, you must select the appropriate surgical method from Principle #1:
            - **If the problematic metric is all_embedded_clauses_ratio (#4):** Use **'Methods for INCREASING Clause Complexity' (1-a)**.
            - **If the problematic metric is average sentence length (#1):** Use **'Methods for INCREASING Sentence Length' (1-c)**.
        - **Rule 2: If the current value is ABOVE the range's maximum:** Your goal is to bring the new value as close as possible to the **MAXIMUM** of the target range. To do this, you must select the appropriate surgical method from Principle #1:
            - **If the problematic metric is all_embedded_clauses_ratio (#4):** Use **'Methods for DECREASING Clause Complexity' (1-b)**.
            - **If the problematic metric is average sentence length (#1):** Use **'Methods for DECREASING Sentence Length' (1-d)**.
    - **Example Scenario**:
        - **Input provided to you**:
        - Problematic Metric: all_embedded_clauses_ratio (#4)
        - Current Value: 0.3
        - Target Range: 0.5 - 0.7
        - Number of modifications needed: 3 sentences
        - **Your Thought Process**: "My task is to edit **AT LEAST 3 sentences** to adjust the metric. The current value (0.3) is below the minimum (0.5), so I must apply Rule 1. I will find 3 sentences where I can use 'Methods for INCREASING Clause Complexity' (1-a) to get the new ratio as close as possible to the minimum target of 0.5."
    3. **Provide the Best Alternative if a Perfect Edit is Impossible**: If it is impossible to make an edit that perfectly meets the target range due to various constraints, you must **present the revised version that comes closest to the target** and briefly explain the limitations encountered.
    4. **Use of Reference Materials:**
    - **Referential Text**: This is your primary stylistic blueprint. **After Principle 2 determines *how many* sentences to modify and the *general method* (e.g., 'Methods for INCREASING Clause Complexity'), you will use the information below to decide the *specific style* of your edits (e.g., which type of clause to add or remove).** **This stylistic guidance is secondary to the primary objectives from Principle 2.** You should only follow rules a and b below if they do not conflict with meeting the minimum modification count and adjusting the target metric.         Your task is to refer to the pre-categorized list of clauses from the *Referential Text* to guide your edits. Specifically:
        a. Emulate Structure Types: You must only use the specific types of clauses present in these provided lists.
         b. Emulate Structural Proportions: Observe the number of examples for each clause category to understand the text's stylistic tendencies. Your goal is to mirror these structural ratios in your edits. **This applies whether you are increasing or decreasing complexity.** For instance, when adding clauses, you should add them in proportions similar to the reference text. Likewise, when removing clauses, you should avoid deleting clauses of only one specific type (e.g., only adverbial clauses) to maintain the original structural balance.
        - **Example Scenario for Structural Proportions:**
            - **Action Required**: Decrease complexity by removing 2 clauses from the text.
            - **Referential Text Proportions**:
            - Adverbial Clauses: 4 examples
            - Relative Clauses: 4 examples
            - Coordinate Clauses: 2 examples
            - **Your Thought Process**: "My task is to reduce complexity by removing 2 clauses. First, I must consult the Referential Text proportions to maintain structural balance. The reference text has a ratio of approximately 2 Adverbial : 2 Relative : 1 Coordinate clause. A poor strategy would be to only remove the 2 coordinate clauses, as this would disproportionately target the least common structure. A better, more balanced approach is to remove one adverbial clause and one relative clause. This method respects the original text's structural diversity as outlined in Principle 4b."
    - **Clause Analysis Criteria**: You must use the following definitions as your technical guide to identify clauses.

    --- Clause Analysis Criteria Begins ---
    1. **Noun clauses** – clauses that function as nouns (e.g., as subject, object, or complement).
    - Must be a full clause with its own subject and verb.
    - *Do not count* infinitival phrases (e.g., "to go", "to understand why") unless they are clearly embedded within a full noun clause.
    - *Do not count* questions unless the question **contains** a noun clause.
    - Examples (✅ Count):
        - "I know **that she left early**."
        - "**What he said** was surprising."
        - "The issue is **whether they will come**."
    - Examples (❌ Don't count):
        - "To understand the problem is important." → (infinitival phrase, not a noun clause)
        - "Why did she leave?" → (yes/no or wh-question without embedded noun clause)

    2. **Relative clauses (adjective clauses)** – clauses that modify a noun, often introduced by *who, that, which, whose*, etc.
    - Must include a subject and verb, and function adjectivally.
    - Examples (✅ Count):
        - "The man **who helped me** was very kind."
        - "She met a girl **whose brother is famous**."
    - Examples (❌ Don't count):
        - "This is the man with the hat." → (no relative clause)

    3. **Adverbial clauses** – clauses that modify a verb, adjective, or clause, expressing time, reason, contrast, condition, etc.
    - Must begin with a **subordinating conjunction** (e.g., because, although, when, if, since, before, after).
    - *Do not count* single adverbs, adverbial phrases, or prepositional phrases.
    - Examples (✅ Count):
        - "She left **because she was tired**."
        - "**When the rain stopped**, we went outside."
    - Examples (❌ Don't count):
        - "To understand why she left, we need context." → (infinitive phrase)
        - "For example, she ran fast." → (prepositional phrase)
        - "Sometimes, I feel tired." → (adverb only)

    4. **Coordinate clauses** – independent clauses joined by **coordinating conjunctions** (*and, but, or, nor, for, so, yet*).
    - Count **only** if **two or more full independent clauses** (each with its own subject and verb) are joined by a coordinating conjunction.
    - Do **not** count compound nouns, compound phrases, or infinitive constructions.
    - Examples (✅ Count – return 1):
        - "I like apples, **but I don't like grapes**."
        - "She studied hard, **and she passed the exam**."
    - Examples (❌ Don't count):
        - "I like apples and bananas." → (noun phrase)
        - "He wants to sing and to dance." → (infinitive phrase)
        - "Strong and brave, he stepped forward." → (adjectival phrase)

    ---

    Here are some full-sentence examples:

    - **"I know that she left early because she was upset."**  
    Noun clauses: that she left early
    Relative clauses: N/A
    Adverbial clauses: because she was upset
    Coordinate clauses: N/A

    - **"The girl who won the race said that she trained every day."**  
    Noun clauses: that she trained every day
    Relative clauses: who won the race
    Adverbial clauses: N/A  
    Coordinate clauses: N/A

    - **"When the movie ended, I realized that I had seen it before."**  
    Noun clauses: that I had seen it before
    Relative clauses: N/A  
    Adverbial clauses: when the movie ended
    Coordinate clauses: N/A

    - **"I like apples, but I don't like grapes."**  
    Noun clauses: N/A  
    Relative clauses: N/A  
    Adverbial clauses: N/A  
    Coordinate clauses: 1

    - **"She studied hard, and she passed the exam, but she was still nervous."**  
    Noun clauses: N/A  
    Relative clauses: N/A  
    Adverbial clauses: N/A  
    Coordinate clauses: 1

    --- Clause Analysis Criteria Ends ---

    # Output
    Your response must contain ONLY the complete, final revised text. Your entire output should be only the revised text, starting with its first word and ending with its last punctuation mark.
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

# 최적 지문 선택 프롬프트
CANDIDATE_SELECTION_PROMPT = """
You are a precise text evaluator selecting the single best revised text from a list.

### Candidates
candidate_1: {candidate_1}
candidate_2: {candidate_2}
candidate_3: {candidate_3}

### Evaluation Criteria (Strict Order):
1. **Foundational Correctness (Pass/Fail):** A candidate MUST be grammatically perfect AND perfectly preserve the original meaning. Any candidate that fails on either of these points is INSTANTLY DISQUALIFIED.
2. **Naturalness and Readability:** Among the candidates that pass Rule #1, the one that is most fluent and natural is better.
3. **Tie-Breaker:** If multiple candidates are equally good, choose the one that integrates its changes most elegantly.

### Response Format:
Respond ONLY with the number of the best candidate (1, 2, or 3).

Examples:
- If candidate 1 is best: "1"
- If candidate 2 is best: "2"
- If candidate 3 is best: "3"

Do not include any explanation, JSON, or additional text. Just the number.
""" 