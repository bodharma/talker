import pytest

from talker.services.voice import CloudVoiceProvider, LocalVoiceProvider, VoiceProviderError


def test_local_provider_init():
    """LocalVoiceProvider initializes without error (models loaded lazily)."""
    provider = LocalVoiceProvider(
        stt_model="tiny", tts_model="en_US-amy-medium", models_dir="models/voice"
    )
    assert provider is not None


def test_cloud_provider_requires_deepgram_key():
    with pytest.raises(VoiceProviderError, match="API key"):
        CloudVoiceProvider(
            deepgram_api_key="",
            elevenlabs_api_key="test",
            deepgram_model="nova-2",
            elevenlabs_model="eleven_multilingual_v2",
            elevenlabs_voice_id="test",
        )


def test_cloud_provider_requires_elevenlabs_key():
    with pytest.raises(VoiceProviderError, match="API key"):
        CloudVoiceProvider(
            deepgram_api_key="test",
            elevenlabs_api_key="",
            deepgram_model="nova-2",
            elevenlabs_model="eleven_multilingual_v2",
            elevenlabs_voice_id="test",
        )


def test_cloud_provider_init_with_keys():
    provider = CloudVoiceProvider(
        deepgram_api_key="test-key",
        elevenlabs_api_key="test-key",
        deepgram_model="nova-2",
        elevenlabs_model="eleven_multilingual_v2",
        elevenlabs_voice_id="test-voice",
    )
    assert provider is not None


def test_available_local_stt_models():
    models = LocalVoiceProvider.available_stt_models()
    assert "tiny" in models
    assert "base" in models
    assert "large-v3" in models


def test_available_local_tts_models():
    models = LocalVoiceProvider.available_tts_models("models/voice")
    assert isinstance(models, list)
