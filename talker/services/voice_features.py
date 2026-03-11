import numpy as np
import parselmouth


def extract_features(
    audio: np.ndarray,
    sample_rate: int = 16000,
    transcript: str | None = None,
) -> dict:
    """Extract voice features from a PCM audio array.

    Returns a dict of features. Handles silent/unvoiced audio gracefully.
    """
    sound = parselmouth.Sound(audio.astype(np.float64), sampling_frequency=sample_rate)
    features: dict = {}

    # Duration
    duration = sound.get_total_duration()
    features["duration"] = round(duration, 3)

    # Pitch (F0)
    pitch = sound.to_pitch(time_step=0.01, pitch_floor=75, pitch_ceiling=500)
    f0_values = pitch.selected_array["frequency"]
    voiced = f0_values[f0_values > 0]
    if len(voiced) > 0:
        features["pitch_mean"] = round(float(np.mean(voiced)), 2)
        features["pitch_std"] = round(float(np.std(voiced)), 2)
        features["pitch_min"] = round(float(np.min(voiced)), 2)
        features["pitch_max"] = round(float(np.max(voiced)), 2)
    else:
        features["pitch_mean"] = 0.0
        features["pitch_std"] = 0.0
        features["pitch_min"] = 0.0
        features["pitch_max"] = 0.0

    # Intensity (volume)
    intensity = sound.to_intensity()
    int_values = intensity.values[intensity.values > 0]
    features["intensity_mean"] = round(float(intensity.get_average()), 2)
    features["intensity_std"] = round(float(np.std(int_values)) if len(int_values) > 0 else 0.0, 2)

    # Voice quality: jitter, shimmer, HNR
    try:
        point_process = parselmouth.call(
            sound, "To PointProcess (periodic, cc)", 75, 500
        )
        features["jitter"] = round(
            parselmouth.call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3), 6
        )
        features["shimmer"] = round(
            parselmouth.call(
                [sound, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6
            ), 6
        )
    except Exception:
        features["jitter"] = 0.0
        features["shimmer"] = 0.0

    try:
        harmonicity = sound.to_harmonicity()
        hnr = parselmouth.call(harmonicity, "Get mean", 0, 0)
        features["hnr"] = round(float(hnr), 2) if not np.isnan(hnr) else 0.0
    except Exception:
        features["hnr"] = 0.0

    # Speech rate (words per second, estimated from transcript)
    if transcript and duration > 0:
        word_count = len(transcript.split())
        features["speech_rate"] = round(word_count / duration, 2)
    else:
        features["speech_rate"] = 0.0

    return features
