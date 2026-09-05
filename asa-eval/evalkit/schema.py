"""Case, advisor-output and result schemas for the AI Stack Advisor eval harness.

Two contracts live here and nowhere else:

  1. EvalCase       -- what a golden test case looks like on disk (YAML).
  2. AdvisorOutput  -- what the advisor must return for the harness to score it.

If you change either, change it here and let the type errors find the callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# --------------------------------------------------------------------------
# Constraint taxonomy (shared with classifier/ -- keep in sync)
# --------------------------------------------------------------------------

class BindingConstraint(str, Enum):
    """What actually gates this project. Only one can be primary."""

    TECHNOLOGY = "technology"          # a genuine stack choice
    REGULATORY = "regulatory"          # licensing, registration, compliance gates it
    COMMERCIAL = "commercial"          # contracts, interconnects, unit economics
    ORGANIZATIONAL = "organizational"  # team capability, headcount, ops maturity
    DATA = "data"                      # data availability, quality or rights
    PRODUCT = "product"                # requirements not settled enough to choose


class ScopeVerdict(str, Enum):
    """How much of this problem a stack recommendation actually addresses."""

    FULL = "full"                    # stack advice substantially solves it
    PARTIAL = "partial"              # stack advice is real but insufficient
    WRONG_QUESTION = "wrong_question"  # a stack recommendation is close to useless


class GoldenStatus(str, Enum):
    DRAFT = "DRAFT"        # machine-drafted, NOT yet ground truth
    REVIEWED = "REVIEWED"  # a human architect signed off; counts toward the score


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


CONFIDENCE_WEIGHT = {Confidence.HIGH: 1.0, Confidence.MEDIUM: 0.6, Confidence.LOW: 0.3}


# --------------------------------------------------------------------------
# Case file schema
# --------------------------------------------------------------------------

@dataclass
class DomainExpectation:
    """Expected outcome for one stack domain (database, cloud, llm_strategy, ...).

    `acceptable` is the set that a competent architect would not object to.
    `preferred` earns a bonus but is never required -- over-fitting the harness
    to one right answer is how you build an advisor that memorises the eval set.
    `unacceptable` is a hard fail: recommending one of these is a defect.
    """

    acceptable: list[str] = field(default_factory=list)
    preferred: str | None = None
    unacceptable: list[str] = field(default_factory=list)
    required_because: str | None = None  # free text, shown in the report on failure


@dataclass
class Golden:
    status: GoldenStatus
    binding_constraint: BindingConstraint
    scope_verdict: ScopeVerdict
    # Substrings/keys that MUST be surfaced somewhere in the output. Recall metric.
    required_flags: list[str] = field(default_factory=list)
    # Things that must NOT be recommended. Any hit is a hard fail (precision metric).
    forbidden: list[str] = field(default_factory=list)
    # Per-domain expectations.
    domains: dict[str, DomainExpectation] = field(default_factory=dict)
    # What a good answer explains. Fed to the LLM judge, never string-matched.
    reasoning_rubric: str = ""
    # Optional: named alternatives the advisor should be seen to have rejected.
    should_rule_out: list[str] = field(default_factory=list)
    reviewer: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None


@dataclass
class CaseInput:
    mode: str                       # "prd" | "questionnaire"
    text: str | None = None         # PRD paste
    answers: dict[str, str] = field(default_factory=dict)  # questionnaire path


@dataclass
class EvalCase:
    id: str
    title: str
    tags: list[str]
    input: CaseInput
    golden: Golden

    @property
    def counts_toward_score(self) -> bool:
        return self.golden.status is GoldenStatus.REVIEWED


# --------------------------------------------------------------------------
# Advisor output schema -- what adapter.advise() must return
# --------------------------------------------------------------------------

@dataclass
class Card:
    """One recommendation card, matching the product's existing output shape."""

    domain: str                  # "database", "cloud", "llm_strategy", ...
    recommendation: str          # the chosen technology/approach, normalised lowercase
    confidence: Confidence
    reasoning: str
    preconditions: list[str] = field(default_factory=list)
    ruled_out: list[str] = field(default_factory=list)   # {name: reason} flattened to "name: reason"
    risks: list[str] = field(default_factory=list)


@dataclass
class AdvisorOutput:
    """The complete response for one case.

    `binding_constraint` and `scope_verdict` are the item-1 additions. An advisor
    that does not yet emit them scores zero on those rules -- which is the point:
    the harness measures the gap before you close it.
    """

    cards: list[Card] = field(default_factory=list)
    binding_constraint: BindingConstraint | None = None
    scope_verdict: ScopeVerdict | None = None
    constraint_rationale: str = ""
    # Anything the advisor said outside the cards (preamble, caveats).
    narrative: str = ""
    # Raw payload, kept for debugging and for the judge to read.
    raw: Any = None

    def all_text(self) -> str:
        """Everything the advisor said, for flag/forbidden matching."""
        parts = [self.narrative, self.constraint_rationale]
        for c in self.cards:
            parts += [c.domain, c.recommendation, c.reasoning]
            parts += c.preconditions + c.ruled_out + c.risks
        return "\n".join(p for p in parts if p).lower()


# --------------------------------------------------------------------------
# Result schema
# --------------------------------------------------------------------------

@dataclass
class RuleResult:
    name: str
    passed: bool
    weight: float
    detail: str = ""

    @property
    def earned(self) -> float:
        return self.weight if self.passed else 0.0


@dataclass
class JudgeResult:
    dimension: str
    score: int          # 1..5
    justification: str


@dataclass
class CaseResult:
    case_id: str
    counted: bool                       # False for DRAFT goldens
    rules: list[RuleResult] = field(default_factory=list)
    judge: list[JudgeResult] = field(default_factory=list)
    calibration_penalty: float = 0.0
    error: str | None = None

    @property
    def rule_score(self) -> float:
        total = sum(r.weight for r in self.rules)
        return (sum(r.earned for r in self.rules) / total) if total else 0.0

    @property
    def judge_score(self) -> float:
        if not self.judge:
            return 0.0
        return sum(j.score for j in self.judge) / (5.0 * len(self.judge))

    def composite(self, rule_weight: float = 0.7) -> float:
        """Rules dominate by default. The judge is a tiebreaker, not the arbiter.

        With the judge disabled the score is the rule score alone, so a perfect
        run reads 1.0 rather than being silently capped at `rule_weight`.
        """
        base = (rule_weight * self.rule_score + (1 - rule_weight) * self.judge_score
                if self.judge else self.rule_score)
        return max(0.0, base - self.calibration_penalty)
