"""Typed tool functions for PydanticAI agents."""

from talker.services.instruments import InstrumentLoader


INSTRUMENT_TRIAGE_PROMPT = """Based on the user's description, select which screening instruments to run.

Available instruments:
{instruments_list}

Analyze the user's concerns and return a JSON list of instrument IDs that are most relevant.
Only select instruments that directly relate to the user's described symptoms.
If unsure, err on the side of including more rather than fewer.

User's description: {user_input}

Return ONLY a JSON array of instrument IDs, e.g. ["phq-9", "gad-7"]"""


def parse_instrument_selection(
    ids: list[str],
    valid_ids: set[str] | None = None,
) -> list[str]:
    """Validate and deduplicate instrument IDs."""
    seen = set()
    result = []
    for id_ in ids:
        id_clean = id_.strip().lower()
        if id_clean in seen:
            continue
        if valid_ids and id_clean not in valid_ids:
            continue
        seen.add(id_clean)
        result.append(id_clean)
    return result


def build_triage_prompt(user_input: str, loader: InstrumentLoader) -> str:
    """Build the prompt for LLM-based instrument selection."""
    instruments = loader.load_all()
    instruments_list = "\n".join(
        f"- {i.metadata.id}: {i.metadata.name} — {i.metadata.description}"
        for i in instruments
    )
    return INSTRUMENT_TRIAGE_PROMPT.format(
        instruments_list=instruments_list,
        user_input=user_input,
    )


def get_score_context(
    instrument_id: str,
    score: int,
    loader: InstrumentLoader,
) -> str:
    """Get human-readable context for a screening score."""
    instrument = loader.load(instrument_id)
    meta = instrument.metadata

    severity = instrument.scoring.thresholds[-1].severity
    for t in instrument.scoring.thresholds:
        if score <= t.max:
            severity = t.severity
            break

    max_score = sum(
        max(o.value for o in instrument.response_options)
        for _ in instrument.questions
    )

    context = (
        f"{meta.name} ({meta.id.upper()})\n"
        f"Your score: {score} out of {max_score}\n"
        f"Severity level: {severity}\n\n"
    )

    thresholds_desc = ", ".join(
        f"{t.severity} (0-{t.max})" for t in instrument.scoring.thresholds
    )
    context += f"Score ranges: {thresholds_desc}\n\n"

    if severity in ("moderate", "moderately severe", "severe", "above threshold"):
        context += (
            f"A score in the {severity} range suggests significant symptoms "
            f"that would benefit from professional evaluation. "
            f"Consider discussing these results with a mental health professional."
        )
    elif severity == "mild":
        context += (
            f"A score in the mild range suggests some symptoms are present. "
            f"Monitoring over time is recommended. If symptoms persist or worsen, "
            f"consider consulting a professional."
        )
    else:
        context += (
            f"A score in the {severity} range suggests minimal symptoms. "
            f"If you're still concerned, a professional consultation can provide clarity."
        )

    return context
