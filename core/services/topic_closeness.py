import json
from pathlib import Path
from typing import Dict, Any, List, Union

from core.llm.client import llm_client_for_profile
from config.labeling_prompt import TOPIC_LABELING_PROMPT
from core.services.semantic_profile import generate_semantic_profile_for_passage


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _PROJECT_ROOT / "config"
_CLOSENESS_SCHEMA = _CONFIG_DIR / "semantic_profile_comp.json"


async def score_topic_closeness(original_profile: Dict[str, Any], generated_profile: Dict[str, Any]) -> Dict[str, Any]:
	"""
	LLM에 기준 점수만 요청하고 total_points는 따로 계산한다.
	"""
	prompt = TOPIC_LABELING_PROMPT.format(
		var_original_semantic_profile=json.dumps(original_profile, ensure_ascii=False, indent=2),
		var_generated_semantic_profile=json.dumps(generated_profile, ensure_ascii=False, indent=2),
	)
	print("prompt", prompt)
	# LLM에는 점수만(JSON) 받도록 response_format 사용
	llm_result = await llm_client_for_profile.generate_text(prompt, output_schema=_CLOSENESS_SCHEMA)
	
	print("llm_result", llm_result)
	def _parse_scoring_json(s: str) -> Dict[str, Any]:
		# 1) 직렬 JSON 파싱 (이중 직렬화 포함)
		try:
			obj = json.loads(s)
			if isinstance(obj, str):
				obj = json.loads(obj)
			if isinstance(obj, dict):
				if "scoring" in obj and isinstance(obj["scoring"], dict):
					return obj
				# 스코어 딕셔너리 자체가 온 경우 래핑
				expected = {
					"discipline_match","subtopic_match","central_focus_match","key_concept_overlap",
					"process_parallel","setting_alignment","purpose_alignment","genre_alignment","penalties"
				}
				if set(obj.keys()).issubset(expected):
					return {"scoring": obj}
		except Exception:
			pass

		# 2) "scoring": { ... } 조각만 온 경우, 뒤의 객체만 추출
		idx = s.find('"scoring"')
		if idx == -1:
			return {"scoring": {}}
		brace_start = s.find('{', idx)
		if brace_start == -1:
			return {"scoring": {}}

		depth = 0
		in_string = False
		escape = False
		end_pos = -1
		for i in range(brace_start, len(s)):
			ch = s[i]
			if in_string:
				if escape:
					escape = False
				elif ch == '\\':
					escape = True
				elif ch == '"':
					in_string = False
				continue
			else:
				if ch == '"':
					in_string = True
				elif ch == '{':
					depth += 1
				elif ch == '}':
					depth -= 1
					if depth == 0:
						end_pos = i
						break

		if end_pos == -1:
			return {"scoring": {}}

		obj_text = s[brace_start:end_pos+1]
		try:
			obj = json.loads(obj_text)
			if isinstance(obj, dict) and "scoring" not in obj:
				return {"scoring": obj}
			return obj if isinstance(obj, dict) else {"scoring": {}}
		except Exception:
			return {"scoring": {}}

	# 교체 후 호출
	parsed = _parse_scoring_json(llm_result)

	# parsed = json.loads(llm_result)

	sc = parsed.get("scoring", {}) or {}

	def _int(v: Any, default: int = 0) -> int:
		try:
			return int(v)
		except Exception:
			return default

	# 각 항목은 정수 점수로 들어온다는 전제 (간소화된 스키마)
	discipline_match = _int(sc.get("discipline_match", 0))
	subtopic_match = _int(sc.get("subtopic_match", 0))
	central_focus_match = _int(sc.get("central_focus_match", 0))
	key_concept_overlap = _int(sc.get("key_concept_overlap", 0))
	process_parallel = _int(sc.get("process_parallel", 0))
	setting_alignment = _int(sc.get("setting_alignment", 0))
	purpose_alignment = _int(sc.get("purpose_alignment", 0))
	genre_alignment = _int(sc.get("genre_alignment", 0))
	penalties_total = _int(sc.get("penalties", 0))  # 음수 합산 값 기대

	points_total = (
		discipline_match
		+ subtopic_match
		+ central_focus_match
		+ key_concept_overlap
		+ process_parallel
		+ setting_alignment
		+ purpose_alignment
		+ genre_alignment
		+ penalties_total
	)

	# total → 1~5 라벨 매핑
	if points_total >= 13:
		label = 5
	elif points_total >= 10:
		label = 4
	elif points_total >= 7:
		label = 3
	elif points_total >= 4:
		label = 2
	else:
		label = 1

	return {
		"scoring": {
			"discipline_match": discipline_match,
			"subtopic_match": subtopic_match,
			"central_focus_match": central_focus_match,
			"key_concept_overlap": key_concept_overlap,
			"process_parallel": process_parallel,
			"setting_alignment": setting_alignment,
			"purpose_alignment": purpose_alignment,
			"genre_alignment": genre_alignment,
			"penalties": penalties_total,
		},
		"total_points": points_total,
		"closeness_label": label,
	}


async def generate_and_score(original_profile: Union[Dict[str, Any], str], passage_text: str) -> Dict[str, Any]:
	"""
	passage로 generated_semantic_profile을 만든 뒤 original과 closeness를 계산한다.
	"""

	generated_profile = await generate_semantic_profile_for_passage(passage_text)
	result = await score_topic_closeness(original_profile, generated_profile)
	# 응답에 생성된 프로필 포함
	result_with_profile = dict(result)
	result_with_profile["generated_semantic_profile"] = generated_profile
	return result_with_profile


async def generate_and_score_batch(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	"""
	배치로 여러 (original_profile, passage_text) 입력을 받아 병렬로 처리한다.
	각 item 스키마: { "original_semantic_profile": Dict[str, Any], "passage_text": str, "request_id"?: str }
	"""
	async def _one(item: Dict[str, Any]) -> Dict[str, Any]:
		try:
			orig = item.get("original_semantic_profile", {}) or {}
			passage = item.get("passage_text", "") or ""
			request_id = item.get("request_id")
			res = await generate_and_score(orig, passage)
			if request_id is not None:
				res["request_id"] = request_id
			return res
		except Exception as e:
			# 오류 시에도 스키마에 맞춘 기본 응답 반환 (+ request_id 에코)
			request_id = item.get("request_id")
			fallback = {
				"scoring": {
					"discipline_match": 0,
					"subtopic_match": 0,
					"central_focus_match": 0,
					"key_concept_overlap": 0,
					"process_parallel": 0,
					"setting_alignment": 0,
					"purpose_alignment": 0,
					"genre_alignment": 0,
					"penalties": 0,
				},
				"total_points": 0,
				"closeness_label": 1,
				"generated_semantic_profile": {
					"discipline": "",
					"subtopic_1": "",
					"subtopic_2": "",
					"central_focus": [],
					"key_concepts": [],
					"processes_structures": None,
					"setting_context": None,
					"purpose_objective": None,
					"genre_form": None,
				},
			}
			if request_id is not None:
				fallback["request_id"] = request_id
			return fallback

	import asyncio
	results = await asyncio.gather(*[ _one(it) for it in items ], return_exceptions=False)
	return results


