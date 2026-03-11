from talker.agents.rag_tools import build_rag_enhanced_prompt


def test_build_rag_enhanced_prompt_includes_context():
    rag_context = "[psychoeducation] PHQ-9 Scoring\nScores above 10 suggest moderate depression."
    base_prompt = "You are a mental health assistant."
    enhanced = build_rag_enhanced_prompt(base_prompt, rag_context)
    assert "CLINICAL KNOWLEDGE" in enhanced
    assert "PHQ-9 Scoring" in enhanced
    assert "mental health assistant" in enhanced


def test_build_rag_enhanced_prompt_no_context():
    enhanced = build_rag_enhanced_prompt("Base prompt.", "")
    assert "CLINICAL KNOWLEDGE" not in enhanced
    assert "Base prompt." in enhanced
