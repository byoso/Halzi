
LOG_LEVEL = "DEBUG"  # DEBUG, INFO, WARNING, ERROR, CRITICAL


APP_NAME = "Halzimir"
VOICE_GENDER = "f"  # m, f
VOICE_LANGUAGE = "fr"  # fr, en

# Ollama
# OLLAMA_MODEL = "mistral"
# OLLAMA_MODEL = "qwen3:14b"
# OLLAMA_MODEL = "qwen3:8b"
OLLAMA_MODEL = "llama3.1:8b"


# VAD
SILENCE_DURATION_FOR_VALIDATION=1000
SAMPLE_RATE = 16000
BLOCK_SIZE = 512  # ~30 ms

# WHISPER CONFIG

LANGUAGE = "fr"  # en, fr
WHISPER_MODEL_SIZE="small"  # tiny, base, small, medium, large
DEVICE="cpu"
COMPUTE_TYPE="int8"


# ==========================
# TEXT TO SPEECH CONFIG
# ==========================


# Piper
if VOICE_LANGUAGE == "fr":
    PIPER_VOICE = "voices/fr/fr_FR-upmc-medium.onnx"
    if VOICE_GENDER == "f":
        SPEAKER_ID = "0"
    if VOICE_GENDER == "m":
        SPEAKER_ID = "1"

if VOICE_LANGUAGE == "en":
    PIPER_VOICE = "voices/en/en_GB-semaine-medium.onnx"
    if VOICE_GENDER == "f":
        SPEAKER_ID = "0"
    if VOICE_GENDER == "m":
        SPEAKER_ID = "1"