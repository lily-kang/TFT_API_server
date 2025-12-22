import sys, os
# Ensure project root is on sys.path when running as a script
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from core.llm.prompt_builder import prompt_builder


def main() -> None:
    # Mock input text
    text = (
        "This is a sample passage. It contains multiple sentences. "
        "We will test the lexical prompt builder. Make a few simple changes."
    )

    # Mock CEFR metrics
    current_cefr_ratio = 0.35  # 35% A1/A2 among NVJD lemmas
    target_min = 0.20
    target_max = 0.30
    direction = "decrease" if current_cefr_ratio > target_max else "increase"
    num_modifications = 3

    # Mock cefr_breakdown structure expected by _generate_vocab_profile
    cefr_breakdown = {
        "a1": {"lemma_count": 5, "lemma_list": ["cat", "dog", "book", "run", "big"]},
        "a2": {"lemma_count": 5, "lemma_list": ["house", "quick", "slow", "water", "school"]},
        "b1": {"lemma_count": 5, "lemma_list": ["consider", "maintain", "assist", "require", "extend"]},
        "b2": {"lemma_count": 4, "lemma_list": ["comprehensive", "derive", "facilitate", "implement"]},
        "c1": {"lemma_count": 3, "lemma_list": ["ubiquitous", "alleviate", "consolidate"]},
        "c2": {"lemma_count": 2, "lemma_list": ["ephemeral", "obfuscate"]},
    }

    messages = prompt_builder.build_lexical_prompt(
        text=text,
        current_cefr_ratio=current_cefr_ratio,
        target_min=target_min,
        target_max=target_max,
        num_modifications=num_modifications,
        direction=direction,
        cefr_breakdown=cefr_breakdown,
    )

    # Print for inspection
    print("=== SYSTEM MESSAGE ===")
    print(messages[0]["content"])  # type: ignore[index]
    print("\n=== USER MESSAGE ===")
    print(messages[1]["content"])  # type: ignore[index]


if __name__ == "__main__":
    sys.exit(main()) 