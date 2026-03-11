"""Tests for the pluggable capability system and voice analysis capability."""

import numpy as np
import pytest

from talker.capabilities.base import BaseCapability
from talker.capabilities.voice_analysis import (
    VoiceAnalysisCapability,
    infer_mood,
)


# ---------------------------------------------------------------------------
# Mood inference (pure function)
# ---------------------------------------------------------------------------


class TestMoodInference:
    def test_neutral_when_no_signals(self):
        features = {"pitch_mean": 150, "pitch_std": 15, "speech_rate": 2.5, "jitter": 0.005}
        result = infer_mood(features)
        assert result["primary_mood"] == "calm" or result["primary_mood"] == "neutral"
        assert 0 <= result["confidence"] <= 1

    def test_anxious_high_pitch_fast_speech(self):
        features = {"pitch_mean": 250, "pitch_std": 40, "speech_rate": 4.0, "jitter": 0.01}
        result = infer_mood(features)
        moods = [m["mood"] for m in result["moods"]]
        assert "anxious" in moods

    def test_stressed_high_jitter(self):
        features = {"pitch_mean": 160, "jitter": 0.03, "shimmer": 0.15, "speech_rate": 2.5}
        result = infer_mood(features)
        moods = [m["mood"] for m in result["moods"]]
        assert "stressed" in moods

    def test_low_energy(self):
        features = {"pitch_mean": 100, "pitch_std": 10, "speech_rate": 1.5, "jitter": 0.005}
        result = infer_mood(features)
        moods = [m["mood"] for m in result["moods"]]
        assert "low_energy" in moods

    def test_agitated(self):
        features = {"pitch_mean": 200, "pitch_std": 60, "intensity_mean": 80, "speech_rate": 3.0}
        result = infer_mood(features)
        moods = [m["mood"] for m in result["moods"]]
        assert "agitated" in moods

    def test_hesitant(self):
        features = {"pitch_mean": 150, "pitch_std": 35, "speech_rate": 1.2, "jitter": 0.01}
        result = infer_mood(features)
        moods = [m["mood"] for m in result["moods"]]
        assert "hesitant" in moods

    def test_calm(self):
        features = {"pitch_mean": 150, "pitch_std": 15, "speech_rate": 2.5, "jitter": 0.005}
        result = infer_mood(features)
        moods = [m["mood"] for m in result["moods"]]
        assert "calm" in moods

    def test_empty_features_returns_neutral(self):
        result = infer_mood({})
        assert result["primary_mood"] == "neutral"

    def test_confidence_scales_with_features(self):
        sparse = infer_mood({"pitch_mean": 200})
        rich = infer_mood({
            "pitch_mean": 200, "pitch_std": 30, "speech_rate": 3.0,
            "jitter": 0.01, "shimmer": 0.05, "hnr": 15, "intensity_mean": 65,
            "duration": 2.5,
        })
        assert rich["confidence"] >= sparse["confidence"]

    def test_multiple_moods_can_cooccur(self):
        # High pitch + fast speech + high jitter = anxious + stressed
        features = {"pitch_mean": 250, "speech_rate": 4.0, "jitter": 0.03, "shimmer": 0.15}
        result = infer_mood(features)
        assert len(result["moods"]) >= 2


# ---------------------------------------------------------------------------
# VoiceAnalysisCapability
# ---------------------------------------------------------------------------


class TestVoiceAnalysisCapability:
    def test_name(self):
        cap = VoiceAnalysisCapability()
        assert cap.name == "voice_analysis"

    def test_is_base_capability(self):
        cap = VoiceAnalysisCapability()
        assert isinstance(cap, BaseCapability)

    def test_room_name_stored(self):
        cap = VoiceAnalysisCapability(room_name="talker-receptionist-abc123")
        assert cap.room_name == "talker-receptionist-abc123"

    @pytest.mark.asyncio
    async def test_process_audio_returns_features_and_mood(self):
        cap = VoiceAnalysisCapability()
        # Generate a simple sine wave (440Hz, 1 second)
        sr = 16000
        t = np.linspace(0, 1.0, sr)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float64)

        result = await cap.process_audio(audio, sr, transcript="hello world")
        assert "features" in result
        assert "mood" in result
        assert "primary_mood" in result["mood"]

    @pytest.mark.asyncio
    async def test_process_audio_updates_instance_state(self):
        cap = VoiceAnalysisCapability()
        sr = 16000
        t = np.linspace(0, 1.0, sr)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float64)

        await cap.process_audio(audio, sr)
        assert cap.latest_analysis != {}
        assert len(cap.analysis_history) >= 1
        assert cap.turn_count == 1

    @pytest.mark.asyncio
    async def test_separate_instances_have_isolated_state(self):
        """Concurrent sessions must not share state."""
        cap1 = VoiceAnalysisCapability(room_name="room-1")
        cap2 = VoiceAnalysisCapability(room_name="room-2")

        sr = 16000
        t = np.linspace(0, 1.0, sr)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float64)

        await cap1.process_audio(audio, sr)
        assert cap1.turn_count == 1
        assert cap2.turn_count == 0
        assert cap2.latest_analysis == {}

    def test_get_context_prompt(self):
        cap = VoiceAnalysisCapability()
        results = {
            "features": {"pitch_mean": 200, "pitch_std": 30, "speech_rate": 3.0, "jitter": 0.01, "hnr": 15},
            "mood": {
                "moods": [{"mood": "calm", "reason": "steady pitch"}],
                "primary_mood": "calm",
                "confidence": 0.75,
            },
        }
        prompt = cap.get_context_prompt(results)
        assert "calm" in prompt
        assert "200" in prompt  # pitch
        assert "Voice Analysis" in prompt

    def test_get_tools_returns_two(self):
        cap = VoiceAnalysisCapability()
        tools = cap.get_tools()
        assert len(tools) == 2

    def test_empty_results_no_context(self):
        cap = VoiceAnalysisCapability()
        prompt = cap.get_context_prompt({})
        assert prompt == ""


# ---------------------------------------------------------------------------
# Tool functions (now per-instance closures)
# ---------------------------------------------------------------------------


class TestVoiceAnalysisTools:
    @pytest.mark.asyncio
    async def test_get_voice_analysis_no_data(self):
        cap = VoiceAnalysisCapability()
        tools = cap.get_tools()
        get_voice_analysis = tools[0]
        result = await get_voice_analysis._func(None)
        assert result["available"] is False

    @pytest.mark.asyncio
    async def test_get_voice_analysis_with_data(self):
        cap = VoiceAnalysisCapability()
        cap.latest_analysis = {
            "features": {"pitch_mean": 180},
            "mood": {"primary_mood": "calm", "confidence": 0.8, "moods": []},
        }
        tools = cap.get_tools()
        get_voice_analysis = tools[0]
        result = await get_voice_analysis._func(None)
        assert result["available"] is True
        assert "features" in result

    @pytest.mark.asyncio
    async def test_get_voice_trend_insufficient_data(self):
        cap = VoiceAnalysisCapability()
        tools = cap.get_tools()
        get_voice_trend = tools[1]
        result = await get_voice_trend._func(None)
        assert result["available"] is False

    @pytest.mark.asyncio
    async def test_get_voice_trend_with_data(self):
        cap = VoiceAnalysisCapability()
        cap.analysis_history.append({
            "features": {"pitch_mean": 200, "speech_rate": 3.0, "jitter": 0.02, "intensity_mean": 70},
            "mood": {"primary_mood": "anxious"},
        })
        cap.analysis_history.append({
            "features": {"pitch_mean": 160, "speech_rate": 2.5, "jitter": 0.01, "intensity_mean": 65},
            "mood": {"primary_mood": "calm"},
        })
        tools = cap.get_tools()
        get_voice_trend = tools[1]
        result = await get_voice_trend._func(None)
        assert result["available"] is True
        assert result["turns_analyzed"] == 2
        assert "pitch_mean" in result["feature_trends"]
        assert result["mood_sequence"] == ["anxious", "calm"]
