from dataclasses import dataclass

from app.silly_engine.silly_orm import (
    Model,
    Mto,
    Mtm,
    Otm,
    Oto
)



@dataclass
class SettingsModel(Model):
    voice_gender: str = "f"  # m, f
    voice_language: str = "en"  # fr, en

    # Ollama
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

    language: str = "en"  # en, fr
    whisper_model_size: str = "small"  # tiny, base, small, medium, large
    device: str = "cpu"
    compute_type: str = "int8"

    class Meta(Model.Meta):
        singleton = True

    @property
    def piper_voice(self) -> str:
        if self.voice_language == "fr":
            return "voices/fr/fr_FR-upmc-medium.onnx"
        if self.voice_language == "en":
            return "voices/en/en_GB-semaine-medium.onnx"
        raise ValueError(f"Unsupported voice language: {self.voice_language}")
