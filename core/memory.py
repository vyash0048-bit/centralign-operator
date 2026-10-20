"""Organizational Memory: Semantic + Episodic store for the CentrAlign runtime."""
from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.models import EpisodicLesson


class CompanyMemoryStore:
    """Manages persistent organizational knowledge in company_memory.json."""

    def __init__(self, memory_path: Path) -> None:
        self.memory_path = memory_path
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load company memory from disk."""
        if self.memory_path.exists():
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "organization_name": "",
            "directory_aliases": {},
            "system_endpoints": {},
            "sops": {},
            "policies": {},
            "episodic_lessons": [],
        }

    def _save(self) -> None:
        """Persist company memory to disk."""
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def reload(self) -> None:
        """Reload memory from disk (picks up changes from prior runs)."""
        self._data = self._load()

    @property
    def policies(self) -> Dict[str, Any]:
        return self._data.get("policies", {})

    @property
    def episodic_lessons(self) -> List[EpisodicLesson]:
        raw = self._data.get("episodic_lessons", [])
        return [EpisodicLesson(**item) for item in raw]

    def resolve_context(self, raw_goal: str) -> Dict[str, Any]:
        """Hydrate context from organizational memory given a raw user goal."""
        context: Dict[str, Any] = {
            "organization_name": self._data.get("organization_name", ""),
            "resolved_aliases": {},
            "system_endpoints": self._data.get("system_endpoints", {}),
            "sop": None,
            "policies": self._data.get("policies", {}),
            "episodic_lessons_count": len(self._data.get("episodic_lessons", [])),
        }

        # Resolve directory aliases mentioned in the goal
        aliases = self._data.get("directory_aliases", {})
        for alias_key, alias_path in aliases.items():
            if alias_key.lower() in raw_goal.lower():
                context["resolved_aliases"][alias_key] = alias_path

        # Always include all aliases for the runtime
        context["all_aliases"] = aliases

        # Attach the most relevant SOP (SOP-FIN-04 for vendor/invoice tasks)
        sops = self._data.get("sops", {})
        for sop_id, sop_body in sops.items():
            if any(kw in raw_goal.lower() for kw in ["vendor", "invoice", "payout", "onboard"]):
                context["sop"] = {"sop_id": sop_id, **sop_body} if isinstance(sop_body, dict) else {"sop_id": sop_id, "content": sop_body}
                break

        return context

    @staticmethod
    def apply_transformation(rule: str, value: Any) -> Any:
        """Apply a named transformation rule to a parameter value."""
        s = str(value)
        if rule == "strip_hyphens_and_spaces_uppercase":
            return s.replace("-", "").replace(" ", "").strip().upper()
        elif rule == "trim_whitespace":
            return s.strip()
        elif rule == "uppercase":
            return s.upper()
        return value

    def apply_episodic_lessons(
        self, tool_name: str, params: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Pre-sanitize parameters using learned episodic lessons.

        Returns:
            Tuple of (sanitized_params, list of applied lesson descriptions).
        """
        sanitized = copy.deepcopy(params)
        applied: List[str] = []

        for lesson in self.episodic_lessons:
            if lesson.tool_name == tool_name and lesson.parameter_name in sanitized:
                original = sanitized[lesson.parameter_name]
                transformed = self.apply_transformation(
                    lesson.transformation_rule, original
                )
                if transformed != original:
                    sanitized[lesson.parameter_name] = transformed
                    applied.append(
                        f"[MEMORY APPLIED] Lesson {lesson.lesson_id}: "
                        f"{lesson.parameter_name} '{original}' -> '{transformed}' "
                        f"(rule: {lesson.transformation_rule})"
                    )

        return sanitized, applied

    def record_lesson(self, lesson: EpisodicLesson) -> None:
        """Persist a new episodic lesson with deduplication."""
        existing = self._data.get("episodic_lessons", [])

        # Deduplicate by tool_name + parameter_name + transformation_rule
        for existing_lesson in existing:
            if (
                existing_lesson.get("tool_name") == lesson.tool_name
                and existing_lesson.get("parameter_name") == lesson.parameter_name
                and existing_lesson.get("transformation_rule") == lesson.transformation_rule
            ):
                return  # Already recorded

        existing.append(lesson.model_dump())
        self._data["episodic_lessons"] = existing
        self._save()
