from pathlib import Path
import yaml
from pydantic import BaseModel, Field
from talker.models.schemas import InstrumentMetadata, ScreeningResult


class InstrumentQuestion(BaseModel):
    id: str
    text: str
    scoring_threshold: int | None = None


class ResponseOption(BaseModel):
    label: str
    value: int


class ScoringThreshold(BaseModel):
    max: int
    severity: str


class FlagRule(BaseModel):
    item: str
    condition: str
    value: int
    flag_as: int
    reason: str


class ScoringConfig(BaseModel):
    method: str
    description: str | None = None
    thresholds: list[ScoringThreshold]


class InstrumentDefinition(BaseModel):
    metadata: InstrumentMetadata
    response_options: list[ResponseOption]
    questions: list[InstrumentQuestion]
    scoring: ScoringConfig
    flags: list[FlagRule] = Field(default_factory=list)
    follow_up_hints: list[str] = Field(default_factory=list)

    def score(self, answers: dict[str, int]) -> ScreeningResult:
        if self.scoring.method == "sum":
            total = sum(answers.get(q.id, 0) for q in self.questions)
        elif self.scoring.method == "asrs_screener":
            total = 0
            for q in self.questions:
                threshold = q.scoring_threshold or 2
                if answers.get(q.id, 0) >= threshold:
                    total += 1
        else:
            total = sum(answers.get(q.id, 0) for q in self.questions)

        severity = self.scoring.thresholds[-1].severity
        for t in self.scoring.thresholds:
            if total <= t.max:
                severity = t.severity
                break

        flagged = []
        for rule in self.flags:
            answer_val = answers.get(rule.item, 0)
            if rule.condition == "greater_than" and answer_val > rule.value:
                flagged.append(rule.flag_as)

        return ScreeningResult(
            instrument_id=self.metadata.id,
            score=total,
            severity=severity,
            raw_answers=answers,
            flagged_items=flagged,
        )


class InstrumentLoader:
    def __init__(self, instruments_dir: str):
        self.instruments_dir = Path(instruments_dir)

    def load(self, instrument_id: str) -> InstrumentDefinition:
        path = self.instruments_dir / f"{instrument_id}.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        return InstrumentDefinition(**data)

    def load_all(self) -> list[InstrumentDefinition]:
        instruments = []
        for path in sorted(self.instruments_dir.glob("*.yaml")):
            with open(path) as f:
                data = yaml.safe_load(f)
            instruments.append(InstrumentDefinition(**data))
        return instruments
