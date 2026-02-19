from dataclasses import dataclass
from typing import Dict

from app.core.settings import settings
from app.orchestrator.states import SessionState, STATE_ORDER


@dataclass
class TransitionResult:
    current_state: SessionState
    next_state: SessionState
    step_index: int


class StateEngine:
    """Deterministic state engine with strict transition order."""

    def __init__(self):
        self.max_transitions = settings.max_state_transitions
        self.state_to_index: Dict[SessionState, int] = {state: idx for idx, state in enumerate(STATE_ORDER)}

    def next_transition(self, current_state: SessionState, step_index: int) -> TransitionResult:
        if step_index >= self.max_transitions:
            raise ValueError("Max state transitions exceeded")

        idx = self.state_to_index[current_state]
        next_idx = min(idx + 1, len(STATE_ORDER) - 1)
        return TransitionResult(
            current_state=current_state,
            next_state=STATE_ORDER[next_idx],
            step_index=step_index + 1,
        )
