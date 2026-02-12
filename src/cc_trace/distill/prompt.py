"""Prompt construction and response parsing for distillation."""

from __future__ import annotations

import json
import logging
import re

from cc_trace.distill.models import DayPrompts, Distillation

logger = logging.getLogger(__name__)

_MAX_TOTAL_CHARS = 6000
_TRUNCATED_PROMPT_LEN = 200

SYSTEM_PROMPT = """\
あなたは「思考パターン分析エンジン」です。
ユーザーが1日にAIに投げたプロンプト一覧を受け取り、その日の思考パターンを抽出してください。

以下のJSON形式で出力してください。JSON以外は出力しないでください。

{
  "core_topics": ["主要トピック1", "主要トピック2", ...],
  "interests": ["関心事1", "関心事2", ...],
  "mood_tension": "その日の気分・テンションの自由記述",
  "energy_level": "high|medium|low|scattered のいずれか",
  "key_questions": ["根底にある問い1", "根底にある問い2", ...],
  "domain_tags": ["engineer", "philosopher", ...]
}

ルール:
- core_topics: 3〜7個。具体的なトピック名。
- interests: 2〜5個。core_topicsより広い関心領域。
- mood_tension: 1〜2文。プロンプトの語調や内容から推測。
- energy_level: high=集中的/生産的、medium=通常、low=疲労/最小限、scattered=多方向に分散。
- key_questions: 2〜5個。プロンプト群の根底にある問い。表面的な質問ではなく本質的な探究。
- domain_tags: engineer/philosopher/life/creative/learning/health/meta から該当するものを選択。
"""


def build_user_prompt(day: DayPrompts) -> str:
    """Format day's prompts into a numbered list for the LLM.

    Truncates individual prompts if total character count exceeds threshold.
    """
    prompts = day.prompts
    total_chars = sum(len(p) for p in prompts)

    if total_chars > _MAX_TOTAL_CHARS:
        prompts = [p[:_TRUNCATED_PROMPT_LEN] for p in prompts]
        logger.debug(
            "Truncated prompts for %s: %d chars -> %d chars",
            day.date,
            total_chars,
            sum(len(p) for p in prompts),
        )

    lines = []
    for i, prompt in enumerate(prompts, 1):
        lines.append(f"[{i}] {prompt}")

    header = f"日付: {day.date} (プロンプト数: {day.prompt_count})"
    if day.gem_names:
        header += f"\n使用Gem: {', '.join(day.gem_names)}"

    return header + "\n\n" + "\n\n".join(lines)


def parse_distillation_response(raw: str, date: str, model: str, prompt_count: int) -> Distillation:
    """Parse LLM response into a Distillation object.

    Tries multiple strategies:
    1. Direct JSON parse
    2. Extract ```json``` fenced block
    3. Find first {...} block
    4. Fallback to empty Distillation
    """
    data = _try_parse_json(raw)
    if data is None:
        data = _try_fenced_json(raw)
    if data is None:
        data = _try_brace_json(raw)
    if data is None:
        logger.warning("Failed to parse distillation response for %s", date)
        return Distillation(date=date, model=model, prompt_count=prompt_count)

    return Distillation(
        date=date,
        core_topics=_list_field(data, "core_topics"),
        interests=_list_field(data, "interests"),
        mood_tension=str(data.get("mood_tension", "")),
        energy_level=_normalize_energy(str(data.get("energy_level", ""))),
        key_questions=_list_field(data, "key_questions"),
        domain_tags=_list_field(data, "domain_tags"),
        prompt_count=prompt_count,
        model=model,
    )


def _try_parse_json(raw: str) -> dict | None:
    try:
        data = json.loads(raw.strip())
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return None


def _try_fenced_json(raw: str) -> dict | None:
    match = re.search(r"```json\s*\n(.*?)```", raw, re.DOTALL)
    if match:
        return _try_parse_json(match.group(1))
    return None


def _try_brace_json(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return _try_parse_json(match.group(0))
    return None


def _list_field(data: dict, key: str) -> list[str]:
    val = data.get(key, [])
    if isinstance(val, list):
        return [str(v) for v in val]
    return []


def _normalize_energy(val: str) -> str:
    val = val.lower().strip()
    if val in ("high", "medium", "low", "scattered"):
        return val
    return ""
