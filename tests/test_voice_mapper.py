from talker.agents.voice_mapper import VoiceAnswerMapping, build_mapping_prompt


def test_voice_answer_mapping_model():
    mapping = VoiceAnswerMapping(value=2, confidence=0.9, reasoning="User said almost every day")
    assert mapping.value == 2
    assert mapping.confidence == 0.9


def test_voice_answer_mapping_confidence_range():
    mapping = VoiceAnswerMapping(value=0, confidence=0.0, reasoning="unclear")
    assert 0.0 <= mapping.confidence <= 1.0


def test_model_validate():
    result = VoiceAnswerMapping.model_validate({
        "value": 3,
        "confidence": 0.85,
        "reasoning": "User clearly indicated nearly every day",
    })
    assert result.value == 3
    assert result.confidence > 0.7


def test_build_mapping_prompt():
    prompt = build_mapping_prompt(
        question="Over the last 2 weeks, how often have you felt down?",
        options=[
            {"value": 0, "text": "Not at all"},
            {"value": 1, "text": "Several days"},
            {"value": 2, "text": "More than half the days"},
            {"value": 3, "text": "Nearly every day"},
        ],
        transcript="yeah pretty much every day",
    )
    assert "every day" in prompt
    assert "Not at all" in prompt
    assert "Nearly every day" in prompt
