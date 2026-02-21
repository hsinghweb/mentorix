from app.skills.base import BaseSkill, SkillMetadata


class LearningPlanBoosterSkill(BaseSkill):
    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="learning-plan-booster",
            version="1.0.0",
            description="Adds explicit pacing and revision constraints to autonomous planning prompts.",
            intent_triggers=["revise plan", "boost plan", "improve learning plan"],
        )

    async def on_run_start(self, initial_prompt: str) -> str:
        return (
            f"{initial_prompt}\n\n"
            "Skill guidance:\n"
            "- Enforce 25-minute focused blocks\n"
            "- Include one spaced-repetition checkpoint\n"
            "- Keep concept progression strictly curriculum-grounded"
        )
