from talker.agents.conversation import ConversationAgent, ConversationContext
from talker.agents.safety import SafetyMonitor, SafetyInterrupt
from talker.agents.screener import ScreenerAgent
from talker.agents.tools import build_triage_prompt, parse_instrument_selection, get_score_context
from talker.models.schemas import ScreeningResult, SessionState
from talker.services.instruments import InstrumentLoader


GREETING = """Welcome to Talker, your psychology pre-assessment assistant.

IMPORTANT: This is NOT a medical or diagnostic tool. The results are screening indicators, not diagnoses. Always consult a qualified mental health professional for proper evaluation.

I can help you explore how you've been feeling by walking you through some validated screening questionnaires, followed by a conversation about the results.

Would you like to:
1. Tell me what's been on your mind (I'll suggest relevant screenings)
2. Run a full checkup (all available screenings)
3. Choose specific screenings to take"""


class Orchestrator:
    """Central coordinator for assessment sessions."""

    def __init__(self, instruments_dir: str = "talker/instruments"):
        self.state = SessionState.CREATED
        self.loader = InstrumentLoader(instruments_dir)
        self.screener = ScreenerAgent(self.loader)
        self.conversation = ConversationAgent()
        self.safety = SafetyMonitor()

        self.instrument_queue: list[str] = []
        self.completed_results: list[ScreeningResult] = []
        self.current_instrument_index: int = 0

    def start(self) -> str:
        self.state = SessionState.INTAKE
        return GREETING

    def check_safety(self, text: str) -> SafetyInterrupt | None:
        return self.safety.check(text)

    def select_instruments(self, instrument_ids: list[str]) -> None:
        self.instrument_queue = instrument_ids
        self.current_instrument_index = 0
        self.state = SessionState.SCREENING
        if self.instrument_queue:
            self.screener.start_instrument(self.instrument_queue[0])

    def select_full_checkup(self) -> None:
        all_instruments = self.loader.load_all()
        self.select_instruments([i.metadata.id for i in all_instruments])

    def get_current_screening_question(self) -> dict | None:
        if self.state != SessionState.SCREENING:
            return None
        q = self.screener.get_current_question()
        if q is None:
            return None
        progress_current, progress_total = self.screener.get_progress()
        return {
            "instrument_id": self.instrument_queue[self.current_instrument_index],
            "question": q.text,
            "question_number": progress_current + 1,
            "total_questions": progress_total,
            "response_options": [
                {"label": o.label, "value": o.value}
                for o in self.screener.current_instrument.response_options
            ],
        }

    def submit_screening_answer(self, value: int) -> dict:
        """Submit an answer. Returns status dict with next action."""
        self.screener.record_answer(value)

        if self.screener.is_complete():
            result = self.screener.get_result()
            if result:
                self.completed_results.append(result)

            self.current_instrument_index += 1
            if self.current_instrument_index < len(self.instrument_queue):
                next_id = self.instrument_queue[self.current_instrument_index]
                self.screener.start_instrument(next_id)
                return {"action": "next_instrument", "instrument_id": next_id}
            else:
                self.state = SessionState.FOLLOW_UP
                return {"action": "screening_complete", "results": self.completed_results}

        return {"action": "next_question"}

    def skip_follow_up(self) -> None:
        self.state = SessionState.SUMMARY

    def get_conversation_context(self) -> ConversationContext:
        return ConversationContext(screening_results=self.completed_results)

    def complete(self) -> None:
        self.state = SessionState.COMPLETED

    def get_triage_prompt(self, user_input: str) -> str:
        """Build prompt for LLM to select instruments based on user's intake."""
        return build_triage_prompt(user_input, self.loader)

    def select_instruments_from_triage(self, instrument_ids: list[str]) -> None:
        """Select instruments after LLM triage. Validates IDs."""
        valid_ids = {i.metadata.id for i in self.loader.load_all()}
        validated = parse_instrument_selection(instrument_ids, valid_ids)
        if not validated:
            self.select_full_checkup()
        else:
            self.select_instruments(validated)

    def get_score_context_for_result(self, instrument_id: str, score: int) -> str:
        """Get interpretation context for a screening score."""
        return get_score_context(instrument_id, score, self.loader)
