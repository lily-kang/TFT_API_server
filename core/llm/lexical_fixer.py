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
from config.lexical_revision_prompt import Lexical_USER_INPUT_TEMPLATE, LEXICAL_FIXING_PROMPT_INCREASE, LEXICAL_FIXING_PROMPT_DECREASE
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
            
            # 어휘 수정 파라미터 계산
            # 현재 CEFR 비율과 목표 범위를 기반으로 수정할 단어 수, 방향, 케이스 등을 계산
            lexical_params = prompt_builder.calculate_lexical_modification_count_nvjd(
                current_ratio=current_cefr_ratio,
                nvjd_total_lemma_count=nvjd_total_lemma_count,
                nvjd_a1a2_lemma_count=nvjd_a1a2_lemma_count,
                master=master,
                tolerance_ratio=tolerance_ratio,
            )
            
            # 계산된 파라미터 추출
            num_modifications = int(lexical_params["num_modifications"])  # type: ignore
            # 방향 우선순위: 계산된 방향 → 호출자 지정값
            direction = lexical_params.get("direction") if lexical_params.get("direction") and lexical_params.get("direction") != "none" else direction  # type: ignore
            target_lower = lexical_params["target_lower"]  # type: ignore
            target_upper = lexical_params["target_upper"]  # type: ignore
            case_label = lexical_params["case"]  # type: ignore (예: "below_range", "within_range", "above_range")
            computed_current_ratio = current_cefr_ratio
            nvjd_total = nvjd_total_lemma_count
            nvjd_a1a2 = nvjd_a1a2_lemma_count
            
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
            
            # 📋 어휘 수정 프롬프트 로깅
            logger.info("=" * 80)
            logger.info("📚 [LEXICAL FIX] 프롬프트 생성")
            logger.info("=" * 80)
            logger.info(f"📊 현재 CEFR A1A2 비율: {computed_current_ratio:.4f}")
            logger.info(f"📊 목표 범위: {target_lower:.4f} ~ {target_upper:.4f}")
            logger.info(f"📊 NVJD 총 렘마: {nvjd_total}, A1A2 렘마: {nvjd_a1a2}")
            logger.info(f"🎯 수정 방향: {direction}, 수정 단어 수: {num_modifications}, Case: {case_label}")
            logger.info(f"🌡️  Temperature: {self.temperature}")
            logger.info("-" * 80)
            logger.info(f"🤖 [SYSTEM 프롬프트]:\n{prompt[0]['content']}")
            logger.info("-" * 80)
            logger.info(f"👤 [USER 프롬프트]:\n{prompt[1]['content']}")
            logger.info("=" * 80)
            
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
        """분석기 응답에서 NVJD 관련 카운트 추출
        
        Note: table_XX는 외부 분석기 API의 응답 테이블 구조
        - table_02: 상세 토큰 정보
        - table_09: 품사 분포
        - table_11: 렘마 지표
        """
        data = raw_analysis.get("data", {})
        text_statistics = data.get("text_statistics", {})
        table_02 = text_statistics.get("table_02_detailed_tokens", {})
        table_09 = text_statistics.get("table_09_pos_distribution", {})
        table_11 = text_statistics.get("table_11_lemma_metrics", {})

        counts = {
            "content_lemmas": int(table_02.get("content_lemmas", 0) or 0),
            "propn_lemma_count": int(table_09.get("propn_lemma_count", 0) or 0),
            "cefr_a1_NVJD_lemma_count": int(table_11.get("cefr_a1_NVJD_lemma_count", 0) or 0),
            "cefr_a2_NVJD_lemma_count": int(table_11.get("cefr_a2_NVJD_lemma_count", 0) or 0),
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
                alts = c.get("alternatives") or []
                if not isinstance(alts, list):
                    alts = []
                if oc and rc:
                    norm_corr.append({
                        "original_clause": oc,
                        "revised_clause": rc,
                        "is_ok": is_ok,
                        "alternatives": alts, 
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
        """여러 후보의 sheet_data를 st_id 기준으로 취합하고 동일 corrections 중복 제거 (alternatives 병합 포함)"""
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
                # corrections 병합 (중복 제거, alternatives 포함)
                exist_map: Dict[tuple, Dict[str, Any]] = {
                    (c.get("original_clause"), c.get("revised_clause")): c for c in target["corrections"]
                }
                for c in (row.get("corrections", []) or []):
                    oc = c.get("original_clause")
                    rc = c.get("revised_clause")
                    if not oc or not rc:
                        continue
                    key = (oc, rc)
                    alts = c.get("alternatives") or []
                    if not isinstance(alts, list):
                        alts = []
                    if key in exist_map:
                        existing = exist_map[key]
                        existing_alts = existing.get("alternatives") or []
                        if not isinstance(existing_alts, list):
                            existing_alts = []
                        # union alternatives (string set)
                        existing["alternatives"] = list({*map(str, existing_alts), *map(str, alts)})
                        # combine is_ok conservatively
                        existing["is_ok"] = bool(existing.get("is_ok", True) and c.get("is_ok", True))
                    else:
                        new_item = {
                            "original_clause": oc,
                            "revised_clause": rc,
                            "is_ok": bool(c.get("is_ok", True)),
                            "alternatives": alts,
                        }
                        target["corrections"].append(new_item)
                        exist_map[key] = new_item
        # st_id 기준 정렬
        return sorted(merged_by_st.values(), key=lambda r: r["st_id"])
    
    async def _generate_lexical_candidates(self, prompt: List[Dict[str, str]]) -> List[str]:
        """어휘 수정 후보 생성 (병렬 처리)"""
        # 병렬로 모든 후보 생성 태스크 생성
        tasks = [
            llm_client.generate_messages(prompt, temperature=self.temperature)
            for _ in range(self.candidates_per_request)
        ]

        logger.debug(f"어휘 후보 {self.candidates_per_request}개를 병렬로 생성 시작...")

        # 병렬 실행 (예외 처리 포함)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 처리
        candidates = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"어휘 후보 {i+1} 생성 실패: {str(result)}")
            else:
                candidates.append(result)
                logger.debug(f"어휘 후보 {i+1} 생성 완료")

        logger.debug(f"병렬 생성 완료: {len(candidates)}개 성공")
        return candidates


# 전역 어휘 수정기 인스턴스
lexical_fixer = LexicalFixer() 