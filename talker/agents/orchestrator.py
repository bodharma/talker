from talker.agents.conversation import ConversationAgent, ConversationContext
from talker.agents.safety import SafetyInterrupt, SafetyMonitor
from talker.agents.screener import ScreenerAgent
from talker.agents.tools import build_triage_prompt, get_score_context, parse_instrument_selection
from talker.models.schemas import SessionData, SessionState
from talker.services.instruments import InstrumentLoader


GREETING = """Welcome to Talker, your psychology pre-assessment assistant.

IMPORTANT: This is NOT a medical or diagnostic tool. The results are screening indicators, not diagnoses. Always consult a qualified mental health professional for proper evaluation.

I can help you explore how you've been feeling by walking you through some validated screening questionnaires, followed by a conversation about the results.

Would you like to:
1. Tell me what's been on your mind (I'll suggest relevant screenings)
2. Run a full checkup (all available screenings)
3. Choose specific screenings to take"""


class Orchestrator:
    """Stateless coordinator for assessment sessions.

    Receives SessionData, performs actions, returns results.
    All state is persisted via SessionRepository by the route handlers.
    """

    def __init__(self, instruments_dir: str = "talker/instruments"):
        self.loader = InstrumentLoader(instruments_dir)
        self.safety = SafetyMonitor()
        self.conversation = ConversationAgent()

    def check_safety(self, text: str) -> SafetyInterrupt | None:
        return self.safety.check(text)

    def get_current_screening_question(self, session: SessionData) -> dict | None:
        if session.state != SessionState.SCREENING:
            return None
        if session.current_instrument_index >= len(session.instrument_queue):
            return None

        instrument_id = session.instrument_queue[session.current_instrument_index]
        screener = self._build_screener(session)

        q = screener.get_current_question()
        if q is None:
            return None

        instrument = self.loader.load(instrument_id)
        progress_current, progress_total = screener.get_progress()
        return {
            "instrument_id": instrument_id,
            "question": q.text,
            "question_number": progress_current + 1,
            "total_questions": progress_total,
            "response_options": [
                {"label": o.label, "value": o.value}
                for o in instrument.response_options
            ],
        }

    def submit_screening_answer(self, session: SessionData, value: int) -> dict:
        """Submit answer. Returns action dict with result and next_index."""
        screener = self._build_screener(session)
        screener.record_answer(value)

        if screener.is_complete():
            result = screener.get_result()
            next_index = session.current_instrument_index + 1

            if next_index < len(session.instrument_queue):
                return {
                    "action": "next_instrument",
                    "instrument_id": session.instrument_queue[next_index],
                    "result": result,
                    "next_index": next_index,
                }
            else:
                return {
                    "action": "screening_complete",
                    "result": result,
                    "next_index": next_index,
                }

        return {
            "action": "next_question",
            "result": None,
            "next_index": session.current_instrument_index,
        }

    def get_conversation_context(self, session: SessionData) -> ConversationContext:
        return ConversationContext(screening_results=session.completed_results)

    def get_all_instrument_ids(self) -> list[str]:
        return [i.metadata.id for i in self.loader.load_all()]

    def get_triage_prompt(self, user_input: str) -> str:
        return build_triage_prompt(user_input, self.loader)

    def parse_triage_result(self, instrument_ids: list[str]) -> list[str]:
        valid_ids = {i.metadata.id for i in self.loader.load_all()}
        validated = parse_instrument_selection(instrument_ids, valid_ids)
        return validated if validated else self.get_all_instrument_ids()

    def get_score_context_for_result(self, instrument_id: str, score: int) -> str:
        return get_score_context(instrument_id, score, self.loader)

    def _build_screener(self, session: SessionData) -> ScreenerAgent:
        """Build a ScreenerAgent and replay answers to restore position."""
        screener = ScreenerAgent(self.loader)
        if session.current_instrument_index >= len(session.instrument_queue):
            return screener

        instrument_id = session.instrument_queue[session.current_instrument_index]
        screener.start_instrument(instrument_id)

        # Replay answers to restore position
        for q in screener.current_instrument.questions:
            if q.id in session.current_answers:
                screener.record_answer(session.current_answers[q.id])
            else:
                break

        return screener
