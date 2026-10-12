"""PolicyEngine: L0 static -> L1 DeBERTa -> L2 Clef.

Maps to executor Outcome downstream:
  allow    -> continue to sandbox/LLM
  escalate -> journal gate_requested -> Pending (HITL inbox)
  deny     -> journal denied, TERMINAL (no human override)
Infra failure (L1/L2 down) raises PolicyError — executor maps to
Error(governance_unavailable), fail-closed per lock 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from warden.policy.layer_clef import ClefScores, ClefUnavailable, FakeClefClient
from warden.policy.layer_deberta import FakeInjectionScorer, InjectionScorer
from warden.policy.layers_static import action_text, find_static_violation


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    ESCALATE = "escalate"
    DENY = "deny"


class PolicyError(RuntimeError):
    """Layer infrastructure failed. Caller must fail closed."""


@dataclass(frozen=True)
class PolicyVerdict:
    decision: PolicyDecision
    reason: str
    policy: str
    layer: str
    scores: dict[str, float]


@dataclass
class PolicyEngine:
    deny_threshold: float = 0.85
    clean_threshold: float = 0.20
    scorer: InjectionScorer | None = None
    clef: FakeClefClient | object = None

    def __post_init__(self) -> None:
        if self.scorer is None:
            self.scorer = FakeInjectionScorer()
        if self.clef is None:
            self.clef = FakeClefClient()

    def evaluate(
        self,
        action_name: str,
        payload: dict[str, object],
        role: str = "operator",
    ) -> PolicyVerdict:
        text = action_text(action_name, payload)

        # L0 — static deny list.
        if (policy_id := find_static_violation(text)) is not None:
            return PolicyVerdict(
                decision=PolicyDecision.DENY,
                reason=f"static rule matched: {policy_id}",
                policy=policy_id,
                layer="L0-static",
                scores={},
            )

        # L1 — DeBERTa injection score.
        assert self.scorer is not None
        try:
            injection = self.scorer.score(text)
        except RuntimeError as exc:
            raise PolicyError(f"L1 deberta unavailable: {exc}") from exc
        if injection.score >= self.deny_threshold:
            return PolicyVerdict(
                decision=PolicyDecision.DENY,
                reason=f"prompt injection p={injection.score:.2f}",
                policy="prompt-injection",
                layer="L1-deberta",
                scores={"injection": injection.score},
            )
        if injection.score <= self.clean_threshold:
            l1_clean = injection.score
        else:
            l1_clean = injection.score  # uncertain band -> consult L2 below

        # L2 — Clef privilege / side-effect / injection re-check.
        try:
            # mypy: clef adapters share judge() shape; typed as object-safe call.
            judge = getattr(self.clef, "judge")
            scores: ClefScores = judge(
                state=text, tool=action_name,
                args=str(payload.get("args", payload)), role=role,
            )
        except ClefUnavailable as exc:
            raise PolicyError(f"L2 clef unavailable: {exc}") from exc

        worst = max(scores.injection, scores.privilege_creep, scores.side_effect)
        merged = {
            "l1_injection": l1_clean,
            "clef_injection": scores.injection,
            "privilege_creep": scores.privilege_creep,
            "side_effect": scores.side_effect,
        }
        if worst >= self.deny_threshold:
            return PolicyVerdict(
                decision=PolicyDecision.DENY,
                reason=f"clef risk p={worst:.2f} ({scores.model})",
                policy="clef-risk",
                layer="L2-clef",
                scores=merged,
            )
        if worst <= self.clean_threshold and l1_clean <= self.clean_threshold:
            return PolicyVerdict(
                decision=PolicyDecision.ALLOW,
                reason="L1 clean + Clef clean",
                policy="default-allow",
                layer="L2-clef",
                scores=merged,
            )
        return PolicyVerdict(
            decision=PolicyDecision.ESCALATE,
            reason=f"uncertain risk p={worst:.2f} needs human",
            policy="uncertain-hitl",
            layer="L2-clef",
            scores=merged,
        )
