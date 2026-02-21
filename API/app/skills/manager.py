from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

from app.skills.base import BaseSkill


class SkillManager:
    def __init__(self):
        self.skills_dir = Path(__file__).resolve().parent / "library"
        self.registry_file = self.skills_dir / "registry.json"
        self.skill_classes: dict[str, type[BaseSkill]] = {}
        self._ensure_paths()

    def _ensure_paths(self) -> None:
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        if not self.registry_file.exists():
            self.registry_file.write_text("{}", encoding="utf-8")

    def scan_and_register(self) -> dict:
        registry = {}
        for item in self.skills_dir.iterdir():
            if not item.is_dir():
                continue
            skill_file = item / "skill.py"
            if not skill_file.exists():
                continue
            klass = self._load_skill_class(skill_file)
            if not klass:
                continue
            instance = klass()
            meta = instance.get_metadata()
            self.skill_classes[meta.name] = klass
            registry[meta.name] = {
                "path": str(skill_file),
                "version": meta.version,
                "description": meta.description,
                "intent_triggers": meta.intent_triggers,
            }
        self.registry_file.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        return registry

    def _load_skill_class(self, file_path: Path) -> type[BaseSkill] | None:
        spec = importlib.util.spec_from_file_location("mentorix_dynamic_skill", file_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for _, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, BaseSkill) and obj is not BaseSkill:
                return obj
        return None

    def get_skill(self, skill_name: str) -> BaseSkill | None:
        if skill_name in self.skill_classes:
            return self.skill_classes[skill_name]()
        registry = json.loads(self.registry_file.read_text(encoding="utf-8"))
        if skill_name not in registry:
            return None
        klass = self._load_skill_class(Path(registry[skill_name]["path"]))
        return klass() if klass else None

    def match_intent(self, query: str) -> str | None:
        normalized = query.lower()
        registry = json.loads(self.registry_file.read_text(encoding="utf-8"))
        for skill_name, info in registry.items():
            for trigger in info.get("intent_triggers", []):
                if trigger.lower() in normalized:
                    return skill_name
        return None


skill_manager = SkillManager()
