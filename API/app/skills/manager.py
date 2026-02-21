from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

from app.skills.base import BaseSkill, SkillMetadata


class GenericSkill(BaseSkill):
    """A skill defined by markdown instructions (SKILL.md) with frontmatter metadata."""

    def __init__(self, md_path: Path, info: dict):
        self.md_path = md_path
        self.info = info

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self.info["name"],
            version=self.info.get("version", "1.0.0"),
            description=self.info.get("description", "Markdown skill"),
            intent_triggers=self.info.get("intent_triggers", []),
        )

    async def on_run_start(self, initial_prompt: str) -> str:
        try:
            content = self.md_path.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
            return f"{initial_prompt}\n\n### Active Skill: {self.info['name']}\n{content}\n"
        except Exception:
            return initial_prompt


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
            md_file = item / "SKILL.md"
            if skill_file.exists():
                klass = self._load_skill_class(skill_file)
                if not klass:
                    continue
                instance = klass()
                meta = instance.get_metadata()
                self.skill_classes[meta.name] = klass
                registry[meta.name] = {
                    "path": str(skill_file),
                    "kind": "python",
                    "version": meta.version,
                    "description": meta.description,
                    "intent_triggers": meta.intent_triggers,
                }
            elif md_file.exists():
                info = self._parse_frontmatter(md_file)
                if not info.get("name"):
                    continue
                registry[info["name"]] = {
                    "path": str(md_file),
                    "kind": "markdown",
                    "version": info.get("version", "1.0.0"),
                    "description": info.get("description", "Markdown skill"),
                    "intent_triggers": info.get("intent_triggers", []),
                }
        self.registry_file.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        return registry

    def _parse_frontmatter(self, md_path: Path) -> dict:
        content = md_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return {}
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}
        raw = parts[1].strip().splitlines()
        parsed: dict = {}
        for line in raw:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                items = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",") if v.strip()]
                parsed[key] = items
            else:
                parsed[key] = value.strip('"').strip("'")
        return parsed

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
        info = registry[skill_name]
        if info.get("kind") == "markdown":
            return GenericSkill(Path(info["path"]), info)
        klass = self._load_skill_class(Path(info["path"]))
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
