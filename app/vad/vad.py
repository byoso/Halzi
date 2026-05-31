#! /usr/bin/env python3

"""
This module detects voice activity in an audio stream
"""
import torch
import sounddevice as sd
import numpy as np
import queue
import time
from typing import Optional
import threading

from app.vad.input_voice import process_audio_buffer
from app.settings import SILENCE_DURATION_FOR_VALIDATION, SAMPLE_RATE, BLOCK_SIZE

# =========================
# CONFIG
# =========================


def is_valid_text(text: str) -> bool:
    if not text:
        return False

    blacklist = [
        "amara.org",
        "sous-titres",
        "subtitles",
        "community"
    ]

    text_lower = text.lower()

    return not any(b in text_lower for b in blacklist)


# =========================
# TTS (speech) activity control
# =========================
_tts_lock = threading.Lock()
_tts_active = False

# Soft pause flag for mic capture. We intentionally avoid stop/start on
# sounddevice streams to prevent PortAudio thread termination issues.
_capture_pause_event = threading.Event()

# current audio stream reference (set when AudioStream context is entered)
_stream_lock = threading.Lock()
_current_stream = None


def set_tts_active(active: bool) -> None:
    """Set whether TTS is currently playing. Thread-safe."""
    global _tts_active
    with _tts_lock:
        _tts_active = bool(active)


def is_tts_active() -> bool:
    """Return True if TTS is currently playing."""
    with _tts_lock:
        return _tts_active


def _set_current_stream(stream_instance) -> None:
    """Internal: set the current AudioStream instance (or None)."""
    global _current_stream
    with _stream_lock:
        _current_stream = stream_instance


def pause_audio_capture() -> None:
    """Soft-pause mic capture without stopping the underlying stream."""
    _capture_pause_event.set()
    with _stream_lock:
        if _current_stream is None:
            return
        try:
            while True:
                _current_stream.queue.get_nowait()
        except queue.Empty:
            pass


def resume_audio_capture() -> None:
    """Resume mic capture after a soft pause."""
    _capture_pause_event.clear()



# =========================
# LOAD SILERO VAD
# =========================
def load_vad():
    """downloads and register the model at ~/.cache/torch/hub """
    bundle = torch.hub.load(
        "snakers4/silero-vad",
        "silero_vad",
        force_reload=False  # do not force reload if already downloaded
    )

    model = bundle[0]  # type: ignore
    utils = bundle[1]  # type: ignore

    (get_speech_timestamps,
     save_audio,
     read_audio,
     VADIterator,
     collect_chunks) = utils

    vad_iterator = VADIterator(
        model,
        sampling_rate=SAMPLE_RATE,
        min_silence_duration_ms=SILENCE_DURATION_FOR_VALIDATION
        )

    return vad_iterator


# =========================
# AUDIO STREAM CLASS
# =========================
class AudioStream:
    def __init__(self, sample_rate=SAMPLE_RATE, block_size=BLOCK_SIZE):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.queue = queue.Queue()

    def callback(self, indata, frames, time_info, status):
        if status:
            print(status)
        if _capture_pause_event.is_set():
            return
        if is_tts_active():
            return
        self.queue.put(indata.copy())

    def __enter__(self):
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.block_size,
            callback=self.callback
        )
        self.stream.start()
        try:
            _set_current_stream(self)
        except NameError:
            pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stream.stop()
        self.stream.close()
        try:
            _set_current_stream(None)
        except NameError:
            pass

    def read(self, timeout: Optional[float] = None):
        return self.queue.get(timeout=timeout)


# =========================
# VAD LOOP
# =========================

def run_vad(vad_iterator, stop_event: Optional[threading.Event] = None, ready_event: Optional[threading.Event] = None):
    for _ in iter_voice_prompts(vad_iterator, stop_event=stop_event, ready_event=ready_event):
        pass


def iter_voice_prompts(vad_iterator=None, stop_event: Optional[threading.Event] = None, ready_event: Optional[threading.Event] = None):
    """Yield validated transcripts from the microphone using VAD + Whisper."""
    if vad_iterator is None:
        vad_iterator = load_vad()

    speech_start = None
    audio_buffer = []

    print("🎤 Listening... (Ctrl+C to stop)")

    with AudioStream() as stream:
        # signal that VAD is active and listening
        if ready_event is not None:
            try:
                ready_event.set()
            except Exception:
                pass

        while True:
            if stop_event is not None and stop_event.is_set():
                return

            if _capture_pause_event.is_set() or is_tts_active():
                time.sleep(0.05)
                continue

            try:
                chunk = stream.read(timeout=0.1)
            except queue.Empty:
                continue

            audio = chunk.reshape(-1)
            tensor = torch.from_numpy(audio)
            speech_dict = vad_iterator(tensor)

            if speech_dict and "start" in speech_dict:
                speech_start = time.time()
                audio_buffer = []
                print("🟢 Speech START")

            if speech_start is not None:
                audio_buffer.append(audio.copy())

            if speech_dict and "end" in speech_dict:
                if not audio_buffer or speech_start is None:
                    speech_start = None
                    audio_buffer = []
                    continue

                full_audio = np.concatenate(audio_buffer)
                print(f"📦 BUFFER SIZE: {len(full_audio)} samples")

                text = process_audio_buffer(audio_buffer=full_audio)
                if is_valid_text(text):
                    print(text)
                    yield text
                else:
                    print("❌ ignored noise")

                duration = time.time() - speech_start
                print(f"🔴 Speech END ({duration:.2f}s)")

                speech_start = None
                audio_buffer = []
# =========================
# MAIN
# =========================
def main():
    vad_iterator = load_vad()
    run_vad(vad_iterator)


def start_vad_thread(timeout: float = 30.0):
    """Start VAD in a daemon thread and wait until it's active.

    Returns a tuple: (thread, ready_event, stop_event, ready_flag)
    """
    ready_event = threading.Event()
    stop_event = threading.Event()

    def target():
        try:
            vad_iterator = load_vad()
            run_vad(vad_iterator, stop_event=stop_event, ready_event=ready_event)
        except Exception as exc:
            # If load_vad or run_vad fails, ensure ready_event not left unset
            if not ready_event.is_set():
                ready_event.set()
            raise

    t = threading.Thread(target=target, daemon=True, name="vad-thread")
    t.start()

    ready = ready_event.wait(timeout=timeout)
    return t, ready_event, stop_event, ready


if __name__ == "__main__":
    main()