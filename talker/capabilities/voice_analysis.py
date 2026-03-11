"""Voice analysis capability — mood and psychological state from audio features.

Wraps the existing voice_features.py service as a pluggable capability.
Any persona can opt into this to get per-turn voice analysis injected
into the LLM context.

Acoustic markers and what they suggest:
    - High pitch + high variability → anxiety, agitation, excitement
    - Low pitch + low variability → fatigue, depression, calm authority
    - High jitter/shimmer → vocal strain, stress, emotional distress
    - Low HNR → breathy/hoarse voice, possible distress or illness
    - Fast speech rate → anxiety, urgency, enthusiasm
    - Slow speech rate → depression, hesitation, thoughtfulness
    - High intensity variability → emotional expressiveness or instability
"""

import logging
from collections import deque
from typing import Any

import numpy as np
from livekit.agents import RunContext, function_tool

from talker.capabilities.base import BaseCapability
from talker.services.voice_features import extract_features

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mood inference from acoustic features
# ---------------------------------------------------------------------------

_MOOD_RULES: list[tuple[str, str, callable]] = [
    # (mood_label, description, predicate(features) -> bool)
    (
        "anxious",
        "elevated pitch and fast speech suggest anxiety or nervousness",
        lambda f: f.get("pitch_mean", 0) > 200 and f.get("speech_rate", 0) > 3.5,
    ),
    (
        "stressed",
        "high jitter and shimmer indicate vocal strain",
        lambda f: f.get("jitter", 0) > 0.02 or f.get("shimmer", 0) > 0.1,
    ),
    (
        "low_energy",
        "low pitch with low speech rate suggests fatigue or low mood",
        lambda f: f.get("pitch_mean", 0) < 120
        and f.get("speech_rate", 0) < 2.0
        and f.get("pitch_mean", 0) > 0,
    ),
    (
        "agitated",
        "high pitch variability and loud volume suggest agitation",
        lambda f: f.get("pitch_std", 0) > 50 and f.get("intensity_mean", 0) > 75,
    ),
    (
        "hesitant",
        "slow speech rate with high pitch variability suggests uncertainty",
        lambda f: f.get("speech_rate", 0) < 1.5
        and f.get("pitch_std", 0) > 30
        and f.get("speech_rate", 0) > 0,
    ),
    (
        "calm",
        "steady pitch and moderate speech rate indicate composure",
        lambda f: f.get("pitch_std", 0) < 20
        and 2.0 <= f.get("speech_rate", 0) <= 3.5
        and f.get("jitter", 0) < 0.01,
    ),
]


def infer_mood(features: dict[str, Any]) -> dict[str, Any]:
    """Infer mood indicators from acoustic features.

    Returns detected moods with explanations. Multiple moods can co-occur.
    Falls back to 'neutral' when no strong signals are detected.
    """
    detected = []
    for label, description, predicate in _MOOD_RULES:
        try:
            if predicate(features):
                detected.append({"mood": label, "reason": description})
        except (KeyError, TypeError):
            continue

    if not detected:
        detected.append({"mood": "neutral", "reason": "no strong vocal indicators detected"})

    # Confidence based on how many features contributed
    non_zero = sum(1 for v in features.values() if isinstance(v, (int, float)) and v > 0)
    confidence = min(1.0, non_zero / 8)  # 8 main features

    return {
        "moods": detected,
        "primary_mood": detected[0]["mood"],
        "confidence": round(confidence, 2),
    }


# ---------------------------------------------------------------------------
# Tool — lets the LLM query accumulated voice analysis
# ---------------------------------------------------------------------------

# Module-level state for the tool to access (set by the capability instance)
_latest_analysis: dict[str, Any] = {}
_analysis_history: deque[dict[str, Any]] = deque(maxlen=20)


@function_tool()
async def get_voice_analysis(
    context: RunContext,
) -> dict[str, Any]:
    """Get the latest voice analysis of the current speaker, including mood indicators,
    pitch, speech rate, and vocal quality. Use this to understand how the person
    is feeling based on how they sound, not just what they say."""
    if not _latest_analysis:
        return {"available": False, "reason": "No voice data analyzed yet."}
    return {"available": True, **_latest_analysis}


@function_tool()
async def get_voice_trend(
    context: RunContext,
) -> dict[str, Any]:
    """Get the trend of the speaker's voice across the conversation so far.
    Shows how their mood and vocal features have changed over multiple turns.
    Useful for noticing if someone is becoming more anxious or calming down."""
    if len(_analysis_history) < 2:
        return {"available": False, "reason": "Need at least 2 voice samples for trend."}

    history = list(_analysis_history)
    first = history[0]
    latest = history[-1]

    trend = {}
    for key in ["pitch_mean", "speech_rate", "jitter", "intensity_mean"]:
        first_val = first.get("features", {}).get(key, 0)
        latest_val = latest.get("features", {}).get(key, 0)
        if first_val > 0:
            change_pct = round((latest_val - first_val) / first_val * 100, 1)
            trend[key] = {
                "first": first_val,
                "latest": latest_val,
                "change_pct": change_pct,
            }

    moods_over_time = [entry.get("mood", {}).get("primary_mood", "unknown") for entry in history]

    return {
        "available": True,
        "turns_analyzed": len(history),
        "feature_trends": trend,
        "mood_sequence": moods_over_time,
    }


# ---------------------------------------------------------------------------
# Capability class
# ---------------------------------------------------------------------------


class VoiceAnalysisCapability(BaseCapability):
    """Analyzes voice acoustics per turn to infer mood and psychological state.

    Plugs into any persona. Provides:
    - Per-turn mood inference from pitch, jitter, shimmer, speech rate
    - Accumulated history for trend analysis
    - Two tools for the LLM: get_voice_analysis, get_voice_trend
    - Context prompt injected before each LLM turn
    """

    @property
    def name(self) -> str:
        return "voice_analysis"

    async def process_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
        transcript: str | None = None,
    ) -> dict[str, Any]:
        features = extract_features(audio, sample_rate, transcript)
        mood = infer_mood(features)

        analysis = {
            "features": features,
            "mood": mood,
        }

        _latest_analysis.clear()
        _latest_analysis.update(analysis)
        _analysis_history.append(analysis)

        log.info(
            "Voice analysis: mood=%s confidence=%.2f pitch=%.0f rate=%.1f",
            mood["primary_mood"],
            mood["confidence"],
            features.get("pitch_mean", 0),
            features.get("speech_rate", 0),
        )

        return analysis

    def get_context_prompt(self, results: dict[str, Any]) -> str:
        mood = results.get("mood", {})
        features = results.get("features", {})

        if not mood:
            return ""

        moods_str = ", ".join(
            f"{m['mood']} ({m['reason']})" for m in mood.get("moods", [])
        )

        return (
            f"\n[Voice Analysis — current turn]\n"
            f"Speaker mood: {moods_str}\n"
            f"Confidence: {mood.get('confidence', 0):.0%}\n"
            f"Pitch: {features.get('pitch_mean', 0):.0f}Hz "
            f"(std: {features.get('pitch_std', 0):.0f}), "
            f"Rate: {features.get('speech_rate', 0):.1f} words/sec, "
            f"Jitter: {features.get('jitter', 0):.4f}, "
            f"HNR: {features.get('hnr', 0):.1f}dB\n"
        )

    def get_tools(self) -> list:
        return [get_voice_analysis, get_voice_trend]
