import asyncio
import math
import pytest

from core.services.text_processing_service_v2 import text_processing_service
from core.llm.client import llm_client
from core.analyzer import analyzer
from models.request import SyntaxFixRequest, MasterMetrics


def make_raw_analysis(avg_len: float, clause_ratio: float, cefr_a1a2_ratio: float, sentence_count: int = 10):
    total_clause_sentences = int(round(clause_ratio * sentence_count))
    # split a1/a2 roughly
    a1 = max(0.0, min(1.0, cefr_a1a2_ratio * 0.5))
    a2 = max(0.0, min(1.0, cefr_a1a2_ratio - a1))
    return {
        "data": {
            "text_statistics": {
                "table_01_basic_overview": {
                    "avg_sentence_length": avg_len,
                    "sentence_count": sentence_count
                },
                "table_02_detailed_tokens": {
                    "lexical_tokens": 100,
                    "content_lemmas": 80
                },
                "table_09_pos_distribution": {
                    "propn_lemma_count": 5
                },
                "table_10_syntax_analysis": {
                    "adverbial_clause_sentences": total_clause_sentences,
                    "coordinate_clause_sentences": 0,
                    "nominal_clause_sentences": 0,
                    "relative_clause_sentences": 0
                },
                "table_11_lemma_metrics": {
                    "cefr_a1_NVJD_lemma_ratio": a1,
                    "cefr_a2_NVJD_lemma_ratio": a2
                }
            }
        }
    }


@pytest.mark.asyncio
async def test_fix_revise_single_original_pass(monkeypatch):
    calls = {"analyze": []}

    async def fake_analyze(text: str, include_syntax: bool = True, llm_model: str = None):
        calls["analyze"].append(include_syntax)
        # Make both syntax and lexical pass
        return make_raw_analysis(avg_len=10.0, clause_ratio=0.30, cefr_a1a2_ratio=0.60)

    monkeypatch.setattr(analyzer, "analyze", fake_analyze)

    # Ensure LLM is not called
    async def fake_generate_multiple_messages_per_temperature(prompt):
        raise AssertionError("LLM should not be called when original passes both")

    monkeypatch.setattr(llm_client, "generate_multiple_messages_per_temperature", fake_generate_multiple_messages_per_temperature)

    req = SyntaxFixRequest(
        request_id="t1",
        text="ORIGINAL_PASS",
        master=MasterMetrics(
            AVG_SENTENCE_LENGTH=10.0,
            All_Embedded_Clauses_Ratio=0.30,
            CEFR_NVJD_A1A2_lemma_ratio=0.60,
        ),
        referential_clauses=""
    )

    res = await text_processing_service.fix_revise_single(req)

    assert res.overall_success is True
    assert res.final_text == req.text
    assert res.candidates_generated == 0
    # Only one analysis call (original)
    assert calls["analyze"] == [True]


@pytest.mark.asyncio
async def test_fix_revise_single_syntax_fail_then_lex_pass(monkeypatch):
    calls = {"analyze": []}

    async def fake_analyze(text: str, include_syntax: bool = True, llm_model: str = None):
        calls["analyze"].append(include_syntax)
        if text == "ORIGINAL_SYNTAX_FAIL":
            # syntax fail: avg length too high, clause ratio too low; lexical value irrelevant here
            return make_raw_analysis(avg_len=20.0, clause_ratio=0.0, cefr_a1a2_ratio=0.30)
        elif text == "CANDIDATE_GOOD_LEX_PASS":
            # syntax pass and lexical pass
            return make_raw_analysis(avg_len=10.0, clause_ratio=0.30, cefr_a1a2_ratio=0.60)
        else:
            # default
            return make_raw_analysis(avg_len=12.0, clause_ratio=0.20, cefr_a1a2_ratio=0.30)

    monkeypatch.setattr(analyzer, "analyze", fake_analyze)

    async def fake_generate_multiple_messages_per_temperature(prompt):
        # Return one good candidate
        return ["CANDIDATE_GOOD_LEX_PASS"]

    monkeypatch.setattr(llm_client, "generate_multiple_messages_per_temperature", fake_generate_multiple_messages_per_temperature)

    req = SyntaxFixRequest(
        request_id="t2",
        text="ORIGINAL_SYNTAX_FAIL",
        master=MasterMetrics(
            AVG_SENTENCE_LENGTH=10.0,
            All_Embedded_Clauses_Ratio=0.30,
            CEFR_NVJD_A1A2_lemma_ratio=0.60,
        ),
        referential_clauses=""
    )

    res = await text_processing_service.fix_revise_single(req)

    assert res.overall_success is True
    assert res.final_text == "CANDIDATE_GOOD_LEX_PASS"
    # Analyzer should be called for original (True) and for each candidate inside syntax_fixer (True)
    assert all(c is True for c in calls["analyze"])  # no include_syntax=False calls


@pytest.mark.asyncio
async def test_fix_revise_single_syntax_fail_then_lex_fail(monkeypatch):
    calls = {"analyze": []}

    async def fake_analyze(text: str, include_syntax: bool = True, llm_model: str = None):
        calls["analyze"].append(include_syntax)
        if text == "ORIGINAL_SYNTAX_FAIL":
            return make_raw_analysis(avg_len=20.0, clause_ratio=0.0, cefr_a1a2_ratio=0.90)
        elif text == "CANDIDATE_GOOD_LEX_FAIL":
            # syntax pass but lexical fail (too high)
            return make_raw_analysis(avg_len=10.0, clause_ratio=0.30, cefr_a1a2_ratio=0.90)
        else:
            return make_raw_analysis(avg_len=12.0, clause_ratio=0.20, cefr_a1a2_ratio=0.90)

    monkeypatch.setattr(analyzer, "analyze", fake_analyze)

    async def fake_generate_multiple_messages_per_temperature(prompt):
        return ["CANDIDATE_GOOD_LEX_FAIL"]

    monkeypatch.setattr(llm_client, "generate_multiple_messages_per_temperature", fake_generate_multiple_messages_per_temperature)

    req = SyntaxFixRequest(
        request_id="t3",
        text="ORIGINAL_SYNTAX_FAIL",
        master=MasterMetrics(
            AVG_SENTENCE_LENGTH=10.0,
            All_Embedded_Clauses_Ratio=0.30,
            CEFR_NVJD_A1A2_lemma_ratio=0.60,
        ),
        referential_clauses=""
    )

    res = await text_processing_service.fix_revise_single(req)

    assert res.overall_success is False
    assert res.final_text == "CANDIDATE_GOOD_LEX_FAIL"
    # Ensure no include_syntax=False calls
    assert all(c is True for c in calls["analyze"])  # only syntax analyses


@pytest.mark.asyncio
async def test_fix_revise_single_syntax_pass_lex_fail_no_llm(monkeypatch):
    calls = {"analyze": []}
    llm_called = {"called": False}

    async def fake_analyze(text: str, include_syntax: bool = True, llm_model: str = None):
        calls["analyze"].append(include_syntax)
        # syntax pass, lexical fail (too low)
        return make_raw_analysis(avg_len=10.0, clause_ratio=0.30, cefr_a1a2_ratio=0.30)

    monkeypatch.setattr(analyzer, "analyze", fake_analyze)

    async def fake_generate_multiple_messages_per_temperature(prompt):
        llm_called["called"] = True
        return ["SHOULD_NOT_BE_USED"]

    monkeypatch.setattr(llm_client, "generate_multiple_messages_per_temperature", fake_generate_multiple_messages_per_temperature)

    req = SyntaxFixRequest(
        request_id="t4",
        text="ORIGINAL_SYNTAX_PASS_LEX_FAIL",
        master=MasterMetrics(
            AVG_SENTENCE_LENGTH=10.0,
            All_Embedded_Clauses_Ratio=0.30,
            CEFR_NVJD_A1A2_lemma_ratio=0.60,
        ),
        referential_clauses=""
    )

    res = await text_processing_service.fix_revise_single(req)

    assert res.overall_success is False
    assert res.final_text == req.text
    # LLM should not be called when syntax passes
    assert llm_called["called"] is False
    # Only one analysis call (original)
    assert calls["analyze"] == [True] 