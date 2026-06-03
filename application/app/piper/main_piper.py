import subprocess
import sounddevice as sd
import json
import numpy as np
import shutil
import sys
from pathlib import Path
from typing import List, Tuple
import threading

from app.database import get_settings

PIPER_VOICE = get_settings().piper_voice
VOICE_LANGUAGE = get_settings().voice_language
SPEAKER_ID = get_settings().piper_speaker_id

BASE_DIR = Path(__file__).parent

PIPER_MODEL = BASE_DIR / PIPER_VOICE


def _resolve_piper_executable() -> str:
    """Resolve Piper CLI path for both terminal and desktop launcher contexts."""
    # Prefer the executable located next to the active Python interpreter
    # (typically inside the application venv).
    # IMPORTANT: do not call .resolve() here; in venvs, python is often a symlink
    # to /usr/bin/pythonX.Y, and resolving would lose the venv bin directory.
    interpreter_dir = Path(sys.executable).parent
    local_piper = interpreter_dir / "piper"
    if local_piper.is_file():
        return str(local_piper)

    # Fallback to the current PATH when running in a shell environment.
    path_piper = shutil.which("piper")
    if path_piper:
        return path_piper

    raise FileNotFoundError(
        "Piper executable not found. Expected in venv next to Python "
        f"({interpreter_dir / 'piper'}) or available in PATH."
    )


PIPER_EXECUTABLE = _resolve_piper_executable()

# Track active Piper subprocesses so they can be terminated on shutdown
_active_procs: List[subprocess.Popen] = []
_procs_lock = threading.Lock()
_playback_lock = threading.Lock()


def _get_model_sample_rate(default_rate: int = 22050) -> int:
    """Return sample rate from the model sidecar JSON, with a safe fallback."""
    sidecar = Path(str(PIPER_MODEL) + ".json")
    try:
        with sidecar.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        cfg = data.get("audio", {}) if isinstance(data, dict) else {}
        rate = cfg.get("sample_rate", default_rate)
        return int(rate)
    except Exception:
        return default_rate


def synthesize_text_to_audio(text: str) -> Tuple[np.ndarray, int]:
    """Synthesize text with Piper and return audio samples in RAM.

    This uses Piper raw stdout mode to avoid temporary WAV files.
    """
    proc = subprocess.Popen(
        [
            PIPER_EXECUTABLE,
            "--model",
            str(PIPER_MODEL),
            "--output_raw",
            "--speaker",
            SPEAKER_ID,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    with _procs_lock:
        _active_procs.append(proc)

    try:
        stdout, stderr = proc.communicate(input=text.encode("utf-8"))

        if proc.returncode not in (0, None):
            err = (stderr or b"").decode("utf-8", errors="ignore").strip()
            raise RuntimeError(f"Piper synthesis failed ({proc.returncode}): {err}")

        if not stdout:
            return np.array([], dtype=np.float32), _get_model_sample_rate()

        # Piper raw mode outputs signed 16-bit mono PCM.
        audio_i16 = np.frombuffer(stdout, dtype=np.int16)
        audio = (audio_i16.astype(np.float32) / 32768.0).copy()
        return audio, _get_model_sample_rate()
    finally:
        with _procs_lock:
            try:
                _active_procs.remove(proc)
            except ValueError:
                pass


def play_audio_buffer(audio: np.ndarray, sample_rate: int) -> None:
    """Play an audio buffer using a blocking output stream."""
    if audio.size == 0:
        return

    # Use explicit blocking stream writes rather than sd.play/sd.wait to reduce
    # PortAudio callback-thread teardown churn under ALSA.
    mono = np.asarray(audio, dtype=np.float32).reshape(-1, 1)

    with _playback_lock:
        with sd.OutputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        ) as stream:
            stream.write(mono)


def text_to_speech(text: str) -> None:
    """Backward-compatible helper: synthesize + play entirely in RAM."""
    audio, sample_rate = synthesize_text_to_audio(text)
    play_audio_buffer(audio, sample_rate)


def stop_all_playback() -> None:
    """Terminate any active Piper subprocesses and stop sounddevice playback."""
    # terminate outstanding synthesis processes
    with _procs_lock:
        for p in list(_active_procs):
            try:
                p.terminate()
            except Exception:
                pass
        _active_procs.clear()
    # stop any ongoing playback
    try:
        sd.stop()
    except Exception:
        pass


if __name__ == "__main__":
    if VOICE_LANGUAGE == "fr":
        text_to_speech(
            "Bonjour, ceci est un test du système de synthèse vocale Piper. Comment allez-vous aujourd'hui ?",
            )
    if VOICE_LANGUAGE == "en":
        text_to_speech(
            "Hello, this is a test of the Piper text-to-speech system. How are you today?",
            )
