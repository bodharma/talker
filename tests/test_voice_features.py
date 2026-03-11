import numpy as np
import pytest

from talker.services.voice_features import extract_features


def _make_sine_wave(freq: float = 200.0, duration: float = 1.0, sr: int = 16000) -> np.ndarray:
    """Generate a sine wave — simulates voiced speech with a clear F0."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float64)


def test_extract_features_returns_dict():
    audio = _make_sine_wave(200.0, 1.0)
    features = extract_features(audio, sample_rate=16000)
    assert isinstance(features, dict)


def test_extract_features_has_pitch():
    audio = _make_sine_wave(200.0, 1.0)
    features = extract_features(audio, sample_rate=16000)
    assert "pitch_mean" in features
    assert "pitch_std" in features
    assert 150 < features["pitch_mean"] < 250


def test_extract_features_has_volume():
    audio = _make_sine_wave(200.0, 1.0)
    features = extract_features(audio, sample_rate=16000)
    assert "intensity_mean" in features
    assert "intensity_std" in features
    assert features["intensity_mean"] > 0


def test_extract_features_has_voice_quality():
    audio = _make_sine_wave(200.0, 1.0)
    features = extract_features(audio, sample_rate=16000)
    assert "jitter" in features
    assert "shimmer" in features
    assert "hnr" in features


def test_extract_features_has_temporal():
    audio = _make_sine_wave(200.0, 1.0)
    features = extract_features(audio, sample_rate=16000, transcript="hello world test")
    assert "duration" in features
    assert "speech_rate" in features
    assert features["duration"] == pytest.approx(1.0, abs=0.1)


def test_extract_features_silent_audio():
    """Silent audio should return features without errors."""
    audio = np.zeros(16000, dtype=np.float64)
    features = extract_features(audio, sample_rate=16000)
    assert isinstance(features, dict)
    assert "pitch_mean" in features
