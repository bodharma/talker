from talker.models.schemas import ScreeningResult
from talker.services.instruments import InstrumentDefinition, InstrumentLoader, InstrumentQuestion


class ScreenerAgent:
    """Runs validated screening instruments. Asks questions exactly as defined."""

    def __init__(self, loader: InstrumentLoader):
        self.loader = loader
        self.current_instrument: InstrumentDefinition | None = None
        self.current_question_index: int = 0
        self.answers: dict[str, int] = {}

    def start_instrument(self, instrument_id: str) -> None:
        self.current_instrument = self.loader.load(instrument_id)
        self.current_question_index = 0
        self.answers = {}

    def get_current_question(self) -> InstrumentQuestion | None:
        if self.current_instrument is None or self.is_complete():
            return None
        return self.current_instrument.questions[self.current_question_index]

    def record_answer(self, value: int) -> None:
        if self.current_instrument is None:
            return
        q = self.current_instrument.questions[self.current_question_index]
        self.answers[q.id] = value
        self.current_question_index += 1

    def is_complete(self) -> bool:
        if self.current_instrument is None:
            return False
        return self.current_question_index >= len(self.current_instrument.questions)

    def get_result(self) -> ScreeningResult | None:
        if self.current_instrument is None or not self.is_complete():
            return None
        return self.current_instrument.score(self.answers)

    def get_progress(self) -> tuple[int, int]:
        if self.current_instrument is None:
            return 0, 0
        return self.current_question_index, len(self.current_instrument.questions)
