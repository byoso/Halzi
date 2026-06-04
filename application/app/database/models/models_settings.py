from dataclasses import dataclass

from app.silly_engine.silly_orm import Model


@dataclass
class SettingsModel(Model):
    voice_gender: str = "f"  # m, f
    voice_language: str = "fr"  # fr, en

    # Ollama
    # ollama_model: str = ""
    # OLLAMA_MODEL = "mistral"  # fast but good at code only, too dumb for just talking
    # OLLAMA_MODEL = "qwen3:14b"  # way too heavy for me !
    # OLLAMA_MODEL = "qwen3:8b"  # not too bad but still a bit slow on my config
    ollama_model: str = "llama3.1:8b"  # not too slow, not to dumb, but not too smart neither

    ollama_host: str = "127.0.0.1"
    ollama_port: int = 11434
    ollama_timeout: float = 1.0

    # VAD
    silence_duration_for_validation: int = 1000
    sample_rate: int = 16000
    block_size: int = 512  # ~30 ms

    # WHISPER CONFIG

    language: str = "fr"  # en, fr
    whisper_model_size: str = "small"  # tiny, base, small, medium, large
    device: str = "cpu"
    compute_type: str = "int8"

    # ===========================

    last_theme_id: str = ""
    last_session_id: str = ""

    class Meta(Model.Meta):
        singleton = True

    @property
    def piper_voice(self) -> str:
        if self.voice_language == "fr":
            return "voices/fr/fr_FR-upmc-medium.onnx"
        if self.voice_language == "en":
            return "voices/en/en_GB-semaine-medium.onnx"
        raise ValueError(f"Unsupported voice language: {self.voice_language}")

    @property
    def piper_speaker_id(self) -> str:
        if self.voice_language in ["fr", "en"]:
            if self.voice_gender == "f":
                return "0"
            if self.voice_gender == "m":
                return "1"
        raise ValueError(f"Unsupported voice language or gender: {self.voice_language}, {self.voice_gender}")