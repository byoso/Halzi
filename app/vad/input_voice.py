import numpy as np
import tempfile
import wave
from faster_whisper import WhisperModel

from app.database import get_settings

settings = get_settings()

LANGUAGE = settings.language
WHISPER_MODEL_SIZE = settings.whisper_model_size
DEVICE = settings.device
COMPUTE_TYPE = settings.compute_type




# =========================
# WHISPER INIT
# =========================
model = WhisperModel(
    model_size_or_path=WHISPER_MODEL_SIZE,
    device=DEVICE,
    compute_type=COMPUTE_TYPE
)


# =========================
# AUDIO BUFFER HANDLING
# =========================
def save_wav(audio_np: np.ndarray, sample_rate: int = 16000) -> str:
    """
    Sauvegarde un numpy audio en fichier wav temporaire
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")

    with wave.open(temp_file.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)

        # conversion float32 -> int16
        audio_int16 = (audio_np * 32767).astype(np.int16)
        wf.writeframes(audio_int16.tobytes())

    return temp_file.name

# =========================
# MAIN FUNCTION (called by VAD)
# =========================
def process_audio_buffer(audio_buffer, sample_rate: int = 16000):
    """
    Reçoit un buffer audio (numpy float32)
    → lance Whisper
    → retourne le texte
    """

    if len(audio_buffer) == 0:
        return ""
    print("BUFFER SIZE:", len(audio_buffer))
    # 1. sauvegarde temporaire wav
    wav_path = save_wav(audio_buffer, sample_rate)

    # 2. transcription
    segments, info = model.transcribe(
        wav_path,
        language=LANGUAGE,
        beam_size=5,
        temperature=0.0,
        vad_filter=False
    )
    # 3. concat texte
    text = " ".join(segment.text for segment in segments).strip()

    # 4. log debug
    print("\n🗣️ TRANSCRIPTION:")

    return text