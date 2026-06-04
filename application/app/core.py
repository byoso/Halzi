#! /usr/bin/env python3


from pathlib import Path
import requests, json
from datetime import datetime
from typing import Tuple, List, Optional, Callable
import re
import shutil
import socket
import subprocess
import time

from app.database import get_settings
from app.silly_engine.silly_orm.item import QItem
from database.db import Themes, Settings

from app.store import store

settings = get_settings()

OLLAMA_MODEL = settings.ollama_model
OLLAMA_HOST = settings.ollama_host
OLLAMA_PORT = settings.ollama_port
OLLAMA_TIMEOUT = settings.ollama_timeout

BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)
MEMORY_TTL = 7 * 24 * 3600  # 7 days in seconds
MEMORY_TTL_ERASE = 30 * 24 * 3600  # 30 days in seconds
INITIAL_CONTEXT_FILE = MEMORY_DIR / "personalities" / "init_personality.md"
THEMES = "Themes"
SESSIONS = "sessions"


def slugify_theme_name(raw_name: str) -> str:
    normalized = raw_name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized.strip("-")


def theme_dir(theme: QItem) -> Path:
    if theme is not None:
        return MEMORY_DIR / SESSIONS / str(theme.q.name)


def ensure_theme_exists(theme: str) -> Path:
    folder = MEMORY_DIR / SESSIONS / theme
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def list_themes() -> List[QItem]:
    return Themes.all()

def get_history(theme: QItem | None) -> List[Tuple[str, str]]:
    if theme is None:
        return []
    # read all files in the memory of the theme and sort by name (which starts with timestamp)
    folder = theme_dir(theme)
    if not folder.exists():
        return []
    files = sorted(folder.glob("*.md"), key=lambda f: f.name)
    history = []
    for file in files:
        with open(file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("**User:**"):
                    text = line[len("**User:**"):].strip()
                    history.append(("User", text))
                elif line.startswith("**Assistant:**"):
                    text = line[len("**Assistant:**"):].strip()
                    history.append(("Assistant", text))
    return history

def create_theme(raw_name: str) -> QItem:
    slug = slugify_theme_name(raw_name)
    if not slug:
        raise ValueError("Invalid theme name")
    folder = MEMORY_DIR / SESSIONS / slug
    if folder.exists():
        raise ValueError("Theme already exists")
    folder.mkdir(parents=True)
    theme = Themes.insert({"name": slug})
    settings = Settings.first()
    assert settings is not None, "Settings should exist in database"
    settings.update(**{"last_theme_id": theme.q._id})
    return theme


def delete_theme(theme: QItem) -> None:
    assert theme.q.name, "Theme must have a name"
    shutil.rmtree(theme_dir(theme), ignore_errors=True)
    Themes.delete(theme)


def save_memory(history, theme: QItem, topic: str = "No topic"):
    topic = topic.strip()
    if not history:
        return
    last_user_input = None
    for role, text in reversed(history):
        if role == "User":
            last_user_input = text
            break
    if last_user_input is None:
        return
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_dir = theme_dir(theme)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"mem_{timestamp}_{topic[:50].replace(' ', '_')}.md"
    with open(filename, "w") as f:
        for role, text in history:
            f.write(f"**{role}:** {text}\n\n")


def is_memory_file_to_load(file):
    if file.stem.startswith("init"):
        return True
    parts = file.stem.split("_")
    if len(parts) < 2:
        return False
    date_str = parts[1]
    date = datetime.strptime(date_str, "%Y%m%d%H%M%S")
    if (datetime.now() - date).total_seconds() > MEMORY_TTL:
        if (datetime.now() - date).total_seconds() > MEMORY_TTL_ERASE:
            file.unlink()  # delete old memory file
        return False
    return True

def load_memory(theme: QItem | None) -> List[Tuple[str, str]]:
    """
    Load memory files from the MEMORY_DIR.
    Returns a list of tuples containing the role and text.
    """
    if theme is None:
        return []
    old_memories = []
    folder = theme_dir(theme)
    folder.mkdir(parents=True, exist_ok=True)
    for file in folder.glob("*.md"):
        if not is_memory_file_to_load(file):
            continue
        with open(file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("**User:**"):
                    text = line[len("**User:**"):].strip()
                    old_memories.append(("User", text))
                elif line.startswith("**Assistant:**"):
                    text = line[len("**Assistant:**"):].strip()
                    old_memories.append(("Assistant", text))
    return old_memories


def load_initial_context() -> str:
    if not INITIAL_CONTEXT_FILE.exists():
        return ""
    return INITIAL_CONTEXT_FILE.read_text(encoding="utf-8").strip()

session_memory = []
initial_context = load_initial_context()

def get_session_memory() -> List[Tuple[str, str]]:
    if store.active_theme is None:
        return []
    memory = load_memory(store.active_theme)
    return memory + session_memory

def build_input_for_api(prompt: str) -> str:
    parts = []
    if initial_context:
        parts.append(initial_context)
        parts.append("")
    for role, text in get_history(store.active_theme) + session_memory:
        if role == "User":
            parts.append(f"User: {text}")
        else:
            parts.append(f"Assistant: {text}")
    parts.append(f"User: {prompt}")
    parts.append("Assistant:")
    return "\n".join(parts)


def _is_ollama_port_open(host: str = OLLAMA_HOST, port: int = OLLAMA_PORT, timeout: float = OLLAMA_TIMEOUT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def ensure_ollama_running(model: str = OLLAMA_MODEL, timeout: int = 30, poll_interval: float = 1.0, log_file: Optional[str] = None) -> bool:
    """Ensure the Ollama service (and given model) is reachable on localhost:11434.

    If the port is not open, attempt to start the model using the `ollama run {model}` CLI
    in a detached process and wait up to `timeout` seconds for the service to become available.

    Returns True if Ollama is reachable (either already running or successfully started),
    False otherwise.
    """
    if _is_ollama_port_open():
        return True

    if log_file is None:
        log_file = f"/tmp/ollama_{model}.log"

    # Ensure the `ollama` CLI exists
    if shutil.which("ollama") is None:
        print(f"ollama CLI not found in PATH; cannot start model '{model}'.")
        return False

    try:
        lf = open(log_file, "ab")
    except Exception:
        lf = None

    try:
        # Start the model in a separate session so it survives this process
        popen = subprocess.Popen(["ollama", "run", model], stdout=lf or subprocess.DEVNULL, stderr=lf or subprocess.DEVNULL, start_new_session=True)
    except Exception as exc:
        if lf:
            lf.close()
        print(f"Failed to start ollama model '{model}': {exc}")
        return False

    # Poll until the port is open or timeout
    start = time.time()
    while time.time() - start < timeout:
        if _is_ollama_port_open():
            if lf:
                lf.close()
            return True
        time.sleep(poll_interval)

    # timed out
    if lf:
        lf.close()
    print(f"Timed out waiting for ollama on port {OLLAMA_PORT} after {OLLAMA_TIMEOUT} seconds. See {log_file} for output.")
    return False

def process_prompt(
    prompt: str,
    display: bool = True,
    record: bool = True,
    on_chunk: Optional[Callable[[str], None]] = None,
) -> Tuple[List[Tuple[str, str]], str]:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": build_input_for_api(prompt),
        "stream": True,
    }
    res = requests.post(f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate", json=payload, stream=True)

    output = ""
    for raw in res.iter_lines(decode_unicode=True):
        if not raw:
            continue
        line = raw.strip()
        if line == "[DONE]":
            break
        try:
            chunk = json.loads(line)
        except Exception:
            continue

        piece = chunk.get("response") or chunk.get("text") or chunk.get("content")
        if not piece and "choices" in chunk and chunk["choices"]:
            piece = chunk["choices"][0].get("text") or chunk["choices"][0].get("content")
        if piece:
            if display:
                print(piece, end="", flush=True)
            if on_chunk is not None:
                try:
                    on_chunk(piece)
                except Exception:
                    pass
            output += piece

    if record:
        session_memory.append(("User", prompt))
        session_memory.append(("Assistant", output))

    return session_memory, output

def list_installed_models(require_running: bool = True) -> List[str]:
    """
    Return installed Ollama model names from /api/tags.
    If require_running is True, try to ensure Ollama is up first.
    """
    if require_running and not _is_ollama_port_open():
        if not ensure_ollama_running(timeout=10):
            return []

    try:
        res = requests.get(
            f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags",
            timeout=OLLAMA_TIMEOUT,
        )
        res.raise_for_status()
        payload = res.json()
    except Exception:
        return []

    names: List[str] = []
    for item in payload.get("models", []):
        name = item.get("name") or item.get("model")
        if name:
            names.append(name)

    return sorted(set(names))