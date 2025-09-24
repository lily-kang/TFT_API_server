import json
import asyncio
import math
from typing import List, Tuple, Dict, Any, Optional
from core.llm.client import llm_client
from core.llm.prompt_builder import prompt_builder
from core.analyzer import analyzer
from core.metrics import metrics_extractor
from core.judge import judge
from config.settings import settings
from config.revision_prompts import Lexical_USER_INPUT_TEMPLATE, LEXICAL_FIXING_PROMPT_INCREASE, LEXICAL_FIXING_PROMPT_DECREASE
from models.request import MasterMetrics, ToleranceRatio
from models.internal import LLMCandidate, LLMResponse
from utils.exceptions import LLMAPIError
from utils.logging import logger


class LexicalFixer:
    """어휘 수정 클래스"""
    
    def __init__(self):
        self.temperature = 0.2  # 어휘 수정은 0.2 고정
        self.candidates_per_request = 3  # 후보 3개 생성
    
    async def fix_lexical_with_params(
        self,
        text: str,
        master: MasterMetrics,
        tolerance_ratio: ToleranceRatio,
        current_cefr_ratio: float,
        direction: str = "increase",  # "increase" or "decrease"
        nvjd_total_lemma_count: Optional[int] = None,
        nvjd_a1a2_lemma_count: Optional[int] = None,
        cefr_breakdown: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict], str, Dict, Any, int]:
        """
        어휘 수정을 수행합니다.
        
        Args:
            text: 수정할 텍스트
            master: 마스터 지표
            tolerance_ratio: 비율 허용 오차
            current_cefr_ratio: 현재 CEFR A1A2 비율
            direction: "increase" (쉽게) 또는 "decrease" (어렵게)
            
        Returns:
            (후보 수정사항 리스트, 선택된 텍스트, 최종 지표, 최종 평가, 생성된 후보 수) 튜플
        """
        try:
            logger.info(f"어휘 수정 시작: {len(text)}글자, 방향={direction}")
            
            # # 목표 범위 계산
            # target_min = master.CEFR_NVJD_A1A2_lemma_ratio - tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio
            # target_max = master.CEFR_NVJD_A1A2_lemma_ratio + tolerance_ratio.CEFR_NVJD_A1A2_lemma_ratio

            calc = prompt_builder.calculate_lexical_modification_count_nvjd(
                current_ratio=current_cefr_ratio,
                nvjd_total_lemma_count=nvjd_total_lemma_count,
                nvjd_a1a2_lemma_count=nvjd_a1a2_lemma_count,
                master=master,
                tolerance_ratio=tolerance_ratio,
            )
            num_modifications = int(calc["num_modifications"])  # type: ignore
            # 방향 우선순위: 계산결과 → 호출자 지정값
            direction = calc.get("direction") if calc.get("direction") and calc.get("direction") != "none" else direction  # type: ignore
            target_lower = calc["target_lower"]  # type: ignore
            target_upper = calc["target_upper"]  # type: ignore
            case_label = calc["case"]  # type: ignore
            computed_current_ratio = current_cefr_ratio
            nvjd_total = nvjd_total_lemma_count
            nvjd_a1a2 = nvjd_a1a2_lemma_count

            # 프롬프트 방향 자동 결정 (현재 비율 기준)
            # 방향은 외부 계산(calc['direction']) 결과를 사용 (재계산하지 않음)
            
            # 프롬프트 구성 (prompt_builder 사용)
            prompt = prompt_builder.build_lexical_prompt(
                text=text,
                current_cefr_ratio=computed_current_ratio,
                target_min=target_lower,
                target_max=target_upper,
                num_modifications=num_modifications,
                direction=direction,
                cefr_breakdown=cefr_breakdown
            )
            
            logger.info(f"어휘 프롬프트 구성 완료, 수정단어수={num_modifications}, temperature={self.temperature}")
            
            # LLM 호출 (temperature 0.2로 3개 후보 생성)
            llm_candidates = await self._generate_lexical_candidates(prompt)
            
            logger.info(f"LLM으로 {len(llm_candidates)}개 후보 생성 완료")
            
            # 후보 파싱 및 통합 sheet_data 생성
            parsed_candidates = []
            sheet_datas = []
            for i, cand_text in enumerate(llm_candidates, start=1):
                parsed = self._parse_lexical_candidate_output(cand_text)
                if parsed.get("parse_ok") and isinstance(parsed.get("sheet_data"), list):
                    sheet_datas.append(parsed["sheet_data"])
                parsed["index"] = i
                parsed_candidates.append(parsed)

            merged_sheet_data = self._merge_sheet_data(sheet_datas) if sheet_datas else []

            # 후보 요약(Revision Summary만)으로 경량화
            candidate_summaries = [
                {"index": p.get("index"), "revision_summary": p.get("revision_summary")}
                for p in parsed_candidates
            ]

            return (
                [],  # modifications - 유지
                text,  # selected_text - 유지
                {  # metrics - 어휘 후보 파싱 결과 포함
                    "NVJD_total_lemma_count": nvjd_total,
                    "NVJD_A1A2_lemma_count": nvjd_a1a2,
                    "CEFR_NVJD_A1A2_lemma_ratio": computed_current_ratio,
                    "target_lower": target_lower,
                    "target_upper": target_upper,
                    "case": case_label,
                    # 후보별 상세 sheet_data는 제외하고 요약만 제공
                    "lexical_candidates": candidate_summaries,
                    "lexical_sheet_data_merged": merged_sheet_data,
                },
                None,
                len(llm_candidates)
            )
            
        except Exception as e:
            logger.error(f"어휘 수정 실패: {str(e)}")
            raise LLMAPIError(f"어휘 수정 중 오류 발생: {str(e)}")
    
    # 제거됨: _calculate_lexical_modifications_from_analysis (외부 계산 사용)

    def _extract_nvjd_counts(self, raw_analysis: Dict[str, Any]) -> Dict[str, int]:
        """분석기 응답에서 NVJD 관련 카운트 추출"""
        data = raw_analysis.get("data", {})
        text_statistics = data.get("text_statistics", {})
        t02 = text_statistics.get("table_02_detailed_tokens", {})
        t09 = text_statistics.get("table_09_pos_distribution", {})
        t11 = text_statistics.get("table_11_lemma_metrics", {})

        counts = {
            "content_lemmas": int(t02.get("content_lemmas", 0) or 0),
            "propn_lemma_count": int(t09.get("propn_lemma_count", 0) or 0),
            "cefr_a1_NVJD_lemma_count": int(t11.get("cefr_a1_NVJD_lemma_count", 0) or 0),
            "cefr_a2_NVJD_lemma_count": int(t11.get("cefr_a2_NVJD_lemma_count", 0) or 0),
        }
        logger.info(f"NVJD 카운트 추출: {counts}")
        return counts

    def _parse_lexical_candidate_output(self, candidate_text: str) -> Dict[str, Any]:
        """lexical 후보 출력 파싱 (두 프롬프트 변형 모두 지원)
        - 선호: { revision_summary, sheet_data: [ {st_id, original_sentence, corrections:[{original_clause,revised_clause,is_ok}]} ] }
        - 대안: [ { original_clause, revised_as, target_word_source_section, target_sentence_number } ]
        반환: { parse_ok, revision_summary, sheet_data, error }
        """
        import re
        result: Dict[str, Any] = {"parse_ok": False, "revision_summary": None, "sheet_data": None, "error": None}
        try:
            # 1) JSON 코드 펜스 우선 탐지
            m = re.search(r"```json\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", candidate_text)
            json_str = None
            if m:
                json_str = m.group(1)
            else:
                # 객체 우선
                m2 = re.search(r"(\{[\s\S]*\})", candidate_text)
                if m2:
                    json_str = m2.group(1)
                else:
                    # 배열 대안
                    m3 = re.search(r"(\[[\s\S]*\])", candidate_text)
                    if m3:
                        json_str = m3.group(1)
            if not json_str:
                result["error"] = "no_json_found"
                return result

            data = json.loads(json_str)
            # 케이스 A: 객체 with sheet_data
            if isinstance(data, dict) and "sheet_data" in data:
                sheet = data.get("sheet_data")
                if isinstance(sheet, list):
                    normalized = self._normalize_sheet_data(sheet)
                    result.update({
                        "parse_ok": True,
                        "revision_summary": data.get("revision_summary"),
                        "sheet_data": normalized
                    })
                    return result
                else:
                    result["error"] = "sheet_data_not_list"
                    return result
            # 케이스 B: 배열 of simple mods
            if isinstance(data, list):
                sheet = self._convert_flat_mods_to_sheet(data)
                result.update({"parse_ok": True, "sheet_data": sheet})
                return result
            result["error"] = "unexpected_json_shape"
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

    def _normalize_sheet_data(self, sheet: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """sheet_data 항목을 표준 형태로 정리"""
        normalized: List[Dict[str, Any]] = []
        for row in sheet:
            st_id = row.get("st_id")
            orig = row.get("original_sentence")
            corrections = row.get("corrections", []) or []
            norm_corr = []
            for c in corrections:
                oc = c.get("original_clause")
                rc = c.get("revised_clause")
                is_ok = bool(c.get("is_ok", True))
                if oc and rc:
                    norm_corr.append({
                        "original_clause": oc,
                        "revised_clause": rc,
                        "is_ok": is_ok
                    })
            if st_id is not None:
                normalized.append({
                    "st_id": int(st_id),
                    "original_sentence": orig,
                    "corrections": norm_corr
                })
        return normalized

    def _convert_flat_mods_to_sheet(self, arr: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """flat 배열 포맷을 sheet_data로 변환"""
        by_st: Dict[int, Dict[str, Any]] = {}
        for item in arr:
            st = int(item.get("target_sentence_number", 0) or 0)
            oc = item.get("original_clause")
            rc = item.get("revised_as")
            if not st or not oc or not rc:
                continue
            row = by_st.setdefault(st, {"st_id": st, "original_sentence": None, "corrections": []})
            row["corrections"].append({
                "original_clause": oc,
                "revised_clause": rc,
                "is_ok": True
            })
        return sorted(by_st.values(), key=lambda r: r["st_id"])

    def _merge_sheet_data(self, sheet_datas: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """여러 후보의 sheet_data를 st_id 기준으로 취합하고 동일 corrections 중복 제거"""
        merged_by_st: Dict[int, Dict[str, Any]] = {}
        for sheet in sheet_datas:
            for row in sheet:
                st = int(row.get("st_id", 0) or 0)
                if not st:
                    continue
                target = merged_by_st.setdefault(st, {"st_id": st, "original_sentence": None, "corrections": []})
                # original_sentence 채우기 (비어있으면 최초 값 사용)
                if not target.get("original_sentence") and row.get("original_sentence"):
                    target["original_sentence"] = row.get("original_sentence")
                # corrections 병합 (중복 제거)
                exist_set = set((c.get("original_clause"), c.get("revised_clause")) for c in target["corrections"])
                for c in row.get("corrections", []) or []:
                    key = (c.get("original_clause"), c.get("revised_clause"))
                    if key not in exist_set and c.get("original_clause") and c.get("revised_clause"):
                        target["corrections"].append({
                            "original_clause": c.get("original_clause"),
                            "revised_clause": c.get("revised_clause"),
                            "is_ok": bool(c.get("is_ok", True))
                        })
                        exist_set.add(key)
        # st_id 기준 정렬
        return sorted(merged_by_st.values(), key=lambda r: r["st_id"])
    
    async def _generate_lexical_candidates(self, prompt: List[Dict[str, str]]) -> List[str]:
        """어휘 수정 후보 생성"""
        candidates = []
        
        for i in range(self.candidates_per_request):
            try:
                response = await llm_client.generate_messages(prompt, temperature=self.temperature)
                candidates.append(response)
                logger.debug(f"어휘 후보 {i+1} 생성 완료")
            except Exception as e:
                logger.warning(f"어휘 후보 {i+1} 생성 실패: {str(e)}")
    
        return candidates


# 전역 어휘 수정기 인스턴스
lexical_fixer = LexicalFixer() 