import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml
import re
from core.llm.client import llm_client_for_profile
from config.profile_gen_prompt import SEMANTIC_PROFILE_GEN_TEMPLATE, SUBTOPIC2_GEN_TEMPLATE
from utils.logging import logger


# Service-level constants
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _PROJECT_ROOT / "config"
_OUTPUT_SCHEMA = _CONFIG_DIR / "output_schema.json"

# YAML 캐시 (성능 최적화: 배치 처리 시 반복 로딩 방지)
_AR_CATEGORY_CACHE: Optional[Dict[str, List[str]]] = None

async def generate_semantic_profile_for_passage(passage_text: str) -> Dict[str, Any]:
	"""
	LLM 2단계 호출로 sample 형태의 의미 프로필을 생성한다. (subtopic_2는 2차 생성)
	"""
	# 1) subtopic_2 제외 프로필 생성
	prompt_1 = SEMANTIC_PROFILE_GEN_TEMPLATE.format(var_passage_text=passage_text)
	
	# 📋 1차 프롬프트 로깅
	logger.info("=" * 80)
	logger.info("🔍 [SEMANTIC PROFILE] 1차 프롬프트 생성")
	logger.info("=" * 80)
	logger.info(f"📄 입력 지문 (처음 500자):\n{passage_text[:500]}...")
	logger.info("-" * 80)
	logger.info(f"📝 1차 프롬프트:\n{prompt_1}")
	logger.info("=" * 80)
	# ------------------------------------------------------------
	first_pass_text = await llm_client_for_profile.generate_text(prompt_1, output_schema=_OUTPUT_SCHEMA)
	profile = _parse_first_pass_profile(first_pass_text)
	print("first_pass_text", first_pass_text)
	# print("profile", profile)
	# 2) subtopic_2 생성을 위한 요약 + AR 카테고리 필터
	summary_text = _summarize_for_subtopic2(profile)
	ar_map = _load_ar_category_map()
	sub1_title = profile.get("subtopic_1", "")
	relevant_items = ar_map.get(sub1_title, [])
	ar_subset_text = f"{sub1_title}: " + ", ".join(relevant_items) if relevant_items else sub1_title

	# 3) subtopic_2 생성
	prompt_2 = SUBTOPIC2_GEN_TEMPLATE.format(
		var_passage_summary=summary_text,
		var_relevant_ar_category_data=ar_subset_text,
	)
	
	# 📋 2차 프롬프트 로깅
	logger.info("=" * 80)
	logger.info("🔍 [SEMANTIC PROFILE] 2차 프롬프트 생성")
	logger.info("=" * 80)
	logger.info(f"📊 1차 프로필 요약:\n{summary_text}")
	logger.info("-" * 80)
	logger.info(f"🏷️  AR 카테고리 데이터:\n{ar_subset_text}")
	logger.info("-" * 80)
	logger.info(f"📝 2차 프롬프트:\n{prompt_2}")
	logger.info("=" * 80)
	# ------------------------------------------------------------
	# print("prompt_2", prompt_2)
	subtopic_2 = (await llm_client_for_profile.generate_text(prompt_2)).strip()
	print("subtopic_2", subtopic_2)

	# 4) 결합
	profile["subtopic_2"] = subtopic_2
	
	# ✅ 최종 프로필 로깅
	logger.info("=" * 80)
	logger.info("✅ [SEMANTIC PROFILE] 생성 완료")
	logger.info("=" * 80)
	logger.info(f"📋 최종 프로필:\n{json.dumps(profile, ensure_ascii=False, indent=2)}")
	logger.info("=" * 80)
	# ------------------------------------------------------------
	return profile


async def generate_semantic_profiles_batch(passages: List[str]) -> List[Dict[str, Any]]:
	"""
	여러 지문에 대해 병렬로 의미 프로필을 생성한다.
	"""
	tasks = [generate_semantic_profile_for_passage(p) for p in passages]
	results = await asyncio.gather(*tasks, return_exceptions=True)
	final: List[Dict[str, Any]] = []
	for res in results:
		if isinstance(res, Exception):
			final.append({
				"discipline": "",
				"subtopic_1": "",
				"subtopic_2": "",
				"central_focus": [],
				"key_concepts": [],
				"error": str(res),
			})
		else:
			final.append(res)
	return final


def _parse_first_pass_profile(text: str) -> Dict[str, Any]:
	"""
	간단한 라인 기반 파서를 통해 1차 프로필을 추출한다.
	- 다양한 라벨 표기 변형 지원: "**1) discipline:**", "1) discipline:", "Discipline:", 등
	- 리스트 필드(central_focus, key_concepts)의 멀티라인 불릿(-, *, •, –) 처리
	- 텍스트 필드의 멀티라인 내용 수집
	"""

	profile: Dict[str, Any] = {
		"discipline": "",
		"subtopic_1": "",
		"central_focus": [],
		"key_concepts": [],
		"processes_structures": None,
		"setting_context": None,
		"purpose_objective": None,
		"genre_form": None,
	}

	# 1) 우선 JSON 파싱 시도 (output_schema 기반 구조 가정)
	try:
		parsed = json.loads(text)
		if isinstance(parsed, dict):
			# 스키마 키 그대로 매핑, 누락 시 기본값 사용
			profile["discipline"] = str(parsed.get("discipline", ""))
			profile["subtopic_1"] = str(parsed.get("subtopic_1", ""))
			cf = parsed.get("central_focus", []) or []
			kc = parsed.get("key_concepts", []) or []
			profile["central_focus"] = [str(x).strip() for x in cf if str(x).strip()]
			profile["key_concepts"] = [str(x).strip() for x in kc if str(x).strip()]
			# nullable 텍스트 필드 처리
			for k in ["processes_structures", "setting_context", "purpose_objective", "genre_form"]:
				v = parsed.get(k, None)
				if v is None:
					profile[k] = None
				else:
					profile[k] = str(v).strip() or None
			return profile
	except Exception:
		pass

	# 2) 텍스트(마크다운) 파싱 폴백: 라벨 변형을 표준 키로 매핑
	label_variants: Dict[str, List[str]] = {
		"discipline": ["discipline"],
		"subtopic_1": ["subtopic_1", "subtopic 1", "subtopic-1"],
		"central_focus": ["central_focus", "central focus", "central-focus"],
		"key_concepts": ["key_concepts", "key concepts", "key-concepts"],
		"processes_structures": [
			"processes_structures",
			"processes/structures",
			"processes structures",
		],
		"setting_context": ["setting_context", "setting/context", "setting context"],
		"purpose_objective": ["purpose/objective", "purpose_objective", "purpose objective"],
		"genre_form": ["genre/form", "genre_form", "genre form"],
	}

	list_fields = {"central_focus", "key_concepts"}

	bullet_prefixes = ("-", "*", "•", "–", "—")

	def sanitize_for_match(s: str) -> str:
		# 소문자화, 마크다운 *와 백틱 제거, 앞 번호(1) 제거
		s2 = s.strip().lower()
		s2 = s2.replace("`", "").replace("**", "").replace("*", "")
		# "1) ", "2)" 패턴 제거
		s2 = re.sub(r"^\s*\d+\)\s*", "", s2)
		# 굵게 표기 후 콜론 앞뒤 공백 정리
		s2 = re.sub(r"\s+", " ", s2)
		return s2

	def find_label_start(line: str) -> Optional[str]:
		norm = sanitize_for_match(line)
		for key, variants in label_variants.items():
			for v in variants:
				if norm.startswith(f"{v}:"):
					return key
		return None

	def content_after_colon(raw_line: str) -> str:
		# 첫 번째 콜론 뒤 텍스트를 반환하되, 마크다운 기호를 정리
		parts = raw_line.split(":", 1)
		if len(parts) == 2:
			val = parts[1].strip()
			# 라벨이 굵게 표기된 경우 남은 ** 제거
			val = val.strip("* ")
			return val
		return ""

	def parse_inline_list(s: str) -> List[str]:
		if not s:
			return []
		if any(s.lstrip().startswith(p) for p in bullet_prefixes):
			# 한 줄에 "- a - b" 형태일 수 있음
			items = [t.strip() for t in s.split("-") if t.strip()]
			return items
		# 콤마 구분 리스트
		return [t.strip() for t in s.split(",") if t.strip()]

	lines = [l.rstrip() for l in text.splitlines() if l.strip()]
	i = 0
	while i < len(lines):
		line = lines[i].strip()
		key = find_label_start(line)
		if not key:
			i += 1
			continue

		inline = content_after_colon(line)

		# 리스트 필드 처리
		if key in list_fields:
			items: List[str] = []
			items.extend(parse_inline_list(inline))

			j = i + 1
			while j < len(lines):
				next_line = lines[j].strip()
				# 다음 라벨 시작이면 중단
				if find_label_start(next_line):
					break
				# 불릿 라인 또는 일반 라인에서 항목 추출
				if next_line.startswith(bullet_prefixes):
					items.append(next_line.lstrip("-*•–— ").strip())
				else:
					# 불릿이 아니어도 콤마/세미콜론 구분을 허용
					parts = re.split(r"[,;]\s*", next_line)
					for p in parts:
						p = p.strip()
						if p:
							items.append(p)
				j += 1

			# 중복/공백 정리
			cleaned = []
			seen = set()
			for it in items:
				val = it.strip("- ")
				if val and val.lower() not in seen:
					seen.add(val.lower())
					cleaned.append(val)
			profile[key] = cleaned
			i = j
			continue

		# 텍스트 필드 처리 (멀티라인)
		val_parts: List[str] = []
		if inline:
			val_parts.append(inline)
		j = i + 1
		while j < len(lines):
			next_line = lines[j].strip()
			if find_label_start(next_line):
				break
			# 불릿으로 이어져도 문장 조각으로 합침
			if next_line.startswith(bullet_prefixes):
				val_parts.append(next_line.lstrip("-*•–— ").strip())
			else:
				val_parts.append(next_line)
			j += 1

		joined = " ".join([p for p in val_parts if p]).strip()
		profile[key] = joined if joined else None
		i = j

	return profile


def _summarize_for_subtopic2(profile: Dict[str, Any]) -> str:
	parts: List[str] = []
	parts.append(f"discipline: {profile.get('discipline','')}")
	parts.append(f"subtopic_1: {profile.get('subtopic_1','')}")
	central_focus = profile.get("central_focus", [])
	if central_focus:
		parts.append("central_focus: " + ", ".join(central_focus))
	key_concepts = profile.get("key_concepts", [])
	if key_concepts:
		parts.append("key_concepts: " + ", ".join(key_concepts))
	for k in ["processes_structures", "setting_context", "purpose_objective", "genre_form"]:
		v = profile.get(k)
		if v:
			parts.append(f"{k}: {v}")
	return "\n".join(parts)


def _load_ar_category_map() -> Dict[str, List[str]]:
	"""
	구조화된 YAML 파일을 로드한다 (캐싱 적용).
	파일: config/ar_category_structured.yaml
	스키마: { "Subtopic_1": ["Option1", "Option2", ...], ... }

	성능 최적화: 첫 호출 시 로드 후 캐시에 저장, 이후 호출은 캐시 반환.
	배치 처리 시 파일 I/O 오버헤드 제거 (50개 배치 → 1번만 로드).
	"""
	global _AR_CATEGORY_CACHE

	# 캐시가 이미 있으면 즉시 반환
	if _AR_CATEGORY_CACHE is not None:
		return _AR_CATEGORY_CACHE

	# 캐시 없음 - 파일 로드
	structured_yaml = _CONFIG_DIR / "ar_category_structured.yaml"
	if not structured_yaml.exists():
		logger.warning(f"AR category YAML 파일 없음: {structured_yaml}")
		_AR_CATEGORY_CACHE = {}
		return _AR_CATEGORY_CACHE

	try:
		with open(structured_yaml, "r", encoding="utf-8") as f:
			data = yaml.safe_load(f) or {}
			if isinstance(data, dict):
				_AR_CATEGORY_CACHE = {k: [str(x) for x in (v or [])] for k, v in data.items()}
			else:
				_AR_CATEGORY_CACHE = {}

		logger.info(f"AR category 맵 로드 완료: {len(_AR_CATEGORY_CACHE)} 카테고리 캐시됨")
		return _AR_CATEGORY_CACHE
	except Exception as e:
		logger.error(f"AR category YAML 로드 실패: {e}")
		_AR_CATEGORY_CACHE = {}
		return _AR_CATEGORY_CACHE


def clear_ar_category_cache():
	"""
	AR category 캐시를 무효화한다.
	YAML 파일 수정 후 재로드가 필요한 경우 사용.
	주로 개발/테스트 환경에서 사용.
	"""
	global _AR_CATEGORY_CACHE
	_AR_CATEGORY_CACHE = None
	logger.info("AR category 캐시 무효화됨") 