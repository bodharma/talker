from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

import numpy as np

log = logging.getLogger(__name__)

FASTER_WHISPER_MODELS = [
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large-v2",
    "large-v3",
    "large-v3-turbo",
]


class VoiceProviderError(Exception):
    pass


class VoiceProvider(Protocol):
    async def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str: ...
    async def synthesize(self, text: str) -> tuple[bytes, int]: ...


class LocalVoiceProvider:
    def __init__(
        self,
        stt_model: str = "base",
        tts_model: str = "en_US-amy-medium",
        models_dir: str = "models/voice",
    ):
        self.stt_model_name = stt_model
        self.tts_model_name = tts_model
        self.models_dir = Path(models_dir)
        self._stt_model = None
        self._tts_voice = None

    def _get_stt_model(self):
        if self._stt_model is None:
            from faster_whisper import WhisperModel

            self._stt_model = WhisperModel(
                self.stt_model_name, device="cpu", compute_type="int8"
            )
        return self._stt_model

    def _get_tts_voice(self):
        if self._tts_voice is None:
            from piper.voice import PiperVoice

            model_path = self.models_dir / f"{self.tts_model_name}.onnx"
            if not model_path.exists():
                raise VoiceProviderError(
                    f"Piper model not found: {model_path}. "
                    f"Download from https://github.com/rhasspy/piper/releases"
                )
            self._tts_voice = PiperVoice.load(str(model_path))
        return self._tts_voice

    async def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        model = self._get_stt_model()
        segments, _ = model.transcribe(
            audio.astype(np.float32), beam_size=5, language="en", vad_filter=True
        )
        return " ".join(seg.text.strip() for seg in segments)

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        voice = self._get_tts_voice()
        audio_chunks = []
        for chunk in voice.synthesize_stream_raw(text):
            audio_chunks.append(chunk)
        return b"".join(audio_chunks), voice.config.sample_rate

    @staticmethod
    def available_stt_models() -> list[str]:
        return list(FASTER_WHISPER_MODELS)

    @staticmethod
    def available_tts_models(models_dir: str) -> list[str]:
        models_path = Path(models_dir)
        if not models_path.exists():
            return []
        return [p.stem for p in sorted(models_path.glob("*.onnx"))]


class CloudVoiceProvider:
    def __init__(
        self,
        deepgram_api_key: str,
        elevenlabs_api_key: str,
        deepgram_model: str = "nova-2",
        elevenlabs_model: str = "eleven_multilingual_v2",
        elevenlabs_voice_id: str = "",
    ):
        if not deepgram_api_key:
            raise VoiceProviderError("Deepgram API key required")
        if not elevenlabs_api_key:
            raise VoiceProviderError("ElevenLabs API key required")
        self.deepgram_api_key = deepgram_api_key
        self.elevenlabs_api_key = elevenlabs_api_key
        self.deepgram_model = deepgram_model
        self.elevenlabs_model = elevenlabs_model
        self.elevenlabs_voice_id = elevenlabs_voice_id
        self._dg_client = None
        self._el_client = None

    def _get_deepgram(self):
        if self._dg_client is None:
            from deepgram import DeepgramClient

            self._dg_client = DeepgramClient(self.deepgram_api_key)
        return self._dg_client

    def _get_elevenlabs(self):
        if self._el_client is None:
            from elevenlabs import ElevenLabs

            self._el_client = ElevenLabs(api_key=self.elevenlabs_api_key)
        return self._el_client

    async def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        dg = self._get_deepgram()
        pcm_int16 = (audio * 32767).astype(np.int16)
        audio_bytes = pcm_int16.tobytes()

        from deepgram import PrerecordedOptions

        source = {"buffer": audio_bytes, "mimetype": "audio/l16;rate=16000;channels=1"}
        options = PrerecordedOptions(model=self.deepgram_model, language="en")
        response = dg.listen.rest.v("1").transcribe_file(source, options)
        return response.results.channels[0].alternatives[0].transcript

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        el = self._get_elevenlabs()
        audio_stream = el.text_to_speech.convert(
            text=text,
            voice_id=self.elevenlabs_voice_id,
            model_id=self.elevenlabs_model,
            output_format="pcm_16000",
        )
        chunks = []
        for chunk in audio_stream:
            chunks.append(chunk)
        return b"".join(chunks), 16000

    @staticmethod
    def available_stt_models() -> list[str]:
        return ["nova-2", "nova-2-medical", "nova-2-general", "enhanced", "base"]

    def available_tts_voices(self) -> list[dict]:
        """Fetch available voices from ElevenLabs API."""
        try:
            el = self._get_elevenlabs()
            response = el.voices.get_all()
            return [
                {"voice_id": v.voice_id, "name": v.name} for v in response.voices
            ]
        except Exception:
            log.warning("Failed to fetch ElevenLabs voices")
            return []


def create_voice_provider(settings) -> LocalVoiceProvider | CloudVoiceProvider:
    """Factory: create the active voice provider from settings."""
    if settings.voice_provider == "cloud":
        return CloudVoiceProvider(
            deepgram_api_key=settings.deepgram_api_key,
            elevenlabs_api_key=settings.elevenlabs_api_key,
            deepgram_model=settings.deepgram_model,
            elevenlabs_model=settings.elevenlabs_model,
            elevenlabs_voice_id=settings.elevenlabs_voice_id,
        )
    return LocalVoiceProvider(
        stt_model=settings.voice_local_stt_model,
        tts_model=settings.voice_local_tts_model,
        models_dir=settings.voice_local_models_dir,
    )
