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
from app.database.db import Themes, Sessions, Settings, SessionMemories
from app.logger import logger

from app.store import store

settings = get_settings()

OLLAMA_MODEL = settings.ollama_model
OLLAMA_HOST = settings.ollama_host
OLLAMA_PORT = settings.ollama_port
OLLAMA_TIMEOUT = settings.ollama_timeout

# BASE_DIR = Path(__file__).parent
BASE_DIR = Path("~/.local/share/geninstaller-applications/.data/halzimir").expanduser()
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)
MEMORY_TTL = 7 * 24 * 3600  # 7 days in seconds
MEMORY_TTL_ERASE = 30 * 24 * 3600  # 30 days in seconds
INITIAL_CONTEXT_FILE = MEMORY_DIR / "personalities" / "default.md"
THEMES = "Themes"
SESSIONS = "sessions"


def slugify_theme_name(raw_name: str) -> str:
    normalized = raw_name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized.strip("-")


def theme_dir(theme: QItem) -> Path:
    if theme is not None:
        return MEMORY_DIR / THEMES /str(theme.q.name) / SESSIONS
    return MEMORY_DIR / THEMES / "default" / SESSIONS

def ensure_theme_exists(theme: str) -> Path:
    folder = MEMORY_DIR / THEMES / theme
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def list_themes() -> List[QItem]:
    return Themes.all()


def save_last_selection() -> None:
    """Persist active theme and session IDs to Settings."""
    settings_record = Settings.first()
    if settings_record is None:
        return
    theme_id = str(store.active_theme.q._id) if store.active_theme is not None else ""
    session_id = str(store.active_session.q._id) if store.active_session is not None else ""
    settings_record.update(last_theme_id=theme_id, last_session_id=session_id)


def restore_last_selection() -> Tuple[QItem | None, QItem | None]:
    """Load previously saved theme and session from Settings. Returns (theme, session)."""
    settings = Settings.first()
    themes = list_themes()
    if not themes:
        return None, None

    theme: QItem | None = None
    if settings is not None and settings.q.last_theme_id:
        theme = next((t for t in themes if str(t.q._id) == str(settings.q.last_theme_id)), None)
    if theme is None:
        theme = themes[0]

    store.active_theme = theme

    session: QItem | None = None
    if settings is not None and settings.q.last_session_id:
        sessions = list_sessions(theme)
        session = next((s for s in sessions if str(s.q._id) == str(settings.q.last_session_id)), None)

    if session is not None:
        activate_session(session)
    else:
        store.active_session = None

    return theme, session


def list_sessions(theme: QItem | None) -> List[QItem]:
    if theme is None:
        return []
    return Sessions.filter(theme_id=theme.q._id).all()


def create_session(theme: QItem, name: str) -> QItem:
    session_name = name.strip()
    if not session_name:
        raise ValueError("Invalid session name")

    session = Sessions.insert({"name": session_name, "theme_id": theme.q._id})
    activate_session(session)
    return session

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
        history.extend(_parse_markdown_history(file.read_text(encoding="utf-8")))
    return history

def create_theme(raw_name: str) -> QItem:
    slug = slugify_theme_name(raw_name)
    if not slug:
        raise ValueError("Invalid theme name")
    folder = MEMORY_DIR / THEMES / slug
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
    theme_sessions = list_sessions(theme)

    if store.active_session is not None:
        active_id = store.active_session.q._id
        if any(session.q._id == active_id for session in theme_sessions):
            clear_active_session()

    for session in theme_sessions:
        delete_session(session)

    theme_root = MEMORY_DIR / THEMES / str(theme.q.name)
    shutil.rmtree(theme_root, ignore_errors=True)
    Themes.delete(theme)


def save_memory(history, theme: QItem, topic: str = "No topic", source_session: QItem | None = None) -> QItem | None:
    topic = topic.strip()
    if not history:
        return None

    last_user_input = None
    for role, text in reversed(history):
        if role == "User":
            last_user_input = text
            break
    if last_user_input is None:
        return None

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Clean the topic name to make it safe for filesystem directory naming
    safe_session_dirname = topic[:50].replace(' ', '_')
    output_dir = theme_dir(theme) / safe_session_dirname
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------------
    # FIX: Filter history to only save NEW messages (the delta)
    # ------------------------------------------------------------------------
    # 1. Read what has already been saved in this directory
    existing_content = ""
    md_files = sorted(output_dir.glob("*.md"))
    for file_path in md_files:
        try:
            existing_content += file_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error(f"Failed to read existing memory file {file_path}: {exc}")

    # 2. Only keep messages that are NOT already in the existing files
    new_messages = []
    for role, text in history:
        message_format = f"**{role}:** {text}"
        # If this exact message structure isn't in our cumulative logs yet, it's new
        if message_format not in existing_content:
            new_messages.append((role, text))

    # If there are no new messages to append, we can safely skip creating an empty file
    if not new_messages:
        logger.debug("No new messages to save for this session snapshot.")
        # We still return the session to ensure database references stay intact
        return source_session if source_session else Sessions.filter(name=topic).first()
    # ------------------------------------------------------------------------

    # The specific file for this new delta snapshot
    filename = output_dir / f"mem_{timestamp}.md"

    try:
        with open(filename, "w") as f:
            for role, text in new_messages: # Save ONLY the new messages
                f.write(f"**{role}:** {text}\n\n")
    except Exception as exc:
        logger.error(f"Failed to save memory to {filename}: {exc}")
        return None

    payload = {
        "name": topic,
        "theme_id": theme.q._id,
    }

    if source_session is not None:
        Sessions.update(payload).filter(_id=source_session.q._id).execute()
        session = source_session
    else:
        session = Sessions.insert(payload)

    # Check if this directory is already registered to avoid duplicate rows in SessionMemories
    existing_memory = SessionMemories.filter(session_id=session.q._id, path=str(output_dir)).first()
    if not existing_memory:
        SessionMemories.insert(
            {
                "path": str(output_dir),
                "session_id": session.q._id,
            }
        )

    if source_session is None:
        activate_session(session)

    return session


def _parse_markdown_history(markdown_content: str) -> List[Tuple[str, str]]:
    history: List[Tuple[str, str]] = []
    current_role: str | None = None
    current_lines: List[str] = []

    def flush_current() -> None:
        nonlocal current_role, current_lines
        if current_role is None:
            return
        history.append((current_role, "\n".join(current_lines).strip()))
        current_role = None
        current_lines = []

    for line in markdown_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("**User:**"):
            flush_current()
            current_role = "User"
            current_lines = [stripped[len("**User:**"):].strip()]
        elif stripped.startswith("**Assistant:**"):
            flush_current()
            current_role = "Assistant"
            current_lines = [stripped[len("**Assistant:**"):].strip()]
        elif current_role is not None:
            current_lines.append(line)

    flush_current()
    return history


def _get_session_file_record(session: QItem) -> QItem | None:
    logger.debug(f"Looking up session file record for session ID {session.q._id}")
    return SessionMemories.filter_first(session_id=session.q._id)


def load_session_markdown(session: QItem) -> str:
    logger.debug(f"loading session memory for {session.q.name}")
    file_record = _get_session_file_record(session)
    logger.debug(f"file record: {file_record}")
    if file_record is None:
        return ""

    # 'path' is now the directory path
    path = Path(str(file_record.q.path))
    logger.debug(f"folder path: {path}")
    if not path.exists() or not path.is_dir():
        return ""

    # 1. Gather all Markdown files inside the session directory
    # sorted() naturally sorts by filename, which orders our timestamps chronologically
    md_files = sorted(path.glob("*.md"))
    if not md_files:
        return ""

    # 2. Read and concatenate the contents of all files
    content_list = []
    for file_path in md_files:
        try:
            content_list.append(file_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error(f"Failed to read memory file {file_path}: {exc}")

    # Join everything with double newlines to keep formatting clean between files
    return "\n\n".join(content_list)


def activate_session(session: QItem | None) -> str:
    store.active_session = session
    session_memory.clear()

    if session is None:
        return ""

    markdown_content = load_session_markdown(session)
    session_memory.extend(_parse_markdown_history(markdown_content))
    return markdown_content


def clear_active_session() -> None:
    activate_session(None)


def delete_session(session: QItem) -> None:
    file_record = _get_session_file_record(session)
    if file_record is not None:
        file_path = Path(str(file_record.q.path))
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError as exc:
                logger.warning(f"Failed to delete session file {file_path}: {exc}")
        SessionMemories.delete(file_record)
    Sessions.delete(session)


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
        old_memories.extend(_parse_markdown_history(file.read_text(encoding="utf-8")))
    return old_memories


def load_initial_context() -> str:
    if not INITIAL_CONTEXT_FILE.exists():
        return ""
    return INITIAL_CONTEXT_FILE.read_text(encoding="utf-8").strip()

session_memory = []
initial_context = load_initial_context()

def get_session_memory() -> List[Tuple[str, str]]:
    if store.active_session is not None:
        return list(session_memory)
    if store.active_theme is None:
        return []
    memory = load_memory(store.active_theme)
    return memory + session_memory

def build_input_for_api(prompt: str) -> str:
    parts = []
    if initial_context:
        parts.append(initial_context)
        parts.append("")
    if store.active_session is not None:
        source_history = list(session_memory)
    else:
        source_history = get_history(store.active_theme) + session_memory

    for role, text in source_history:
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
        logger.error(f"ollama CLI not found in PATH; cannot start model '{model}'.")
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
        logger.error(f"Failed to start ollama model '{model}': {exc}")
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
    logger.error(f"Timed out waiting for ollama on port {OLLAMA_PORT} after {OLLAMA_TIMEOUT} seconds. See {log_file} for output.")
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
                logger.debug(piece)
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


def list_folder_paths(base_path: str, paths: list[str] | None = None) -> list[str]:
    if paths is None:
        paths = [base_path]
    if Path(base_path).is_dir():
        for entry in Path(base_path).iterdir():
            if entry.is_dir():
                paths.append(str(entry))
                list_folder_paths(str(entry), paths)
            else:
                paths.append(str(entry))
    return paths
