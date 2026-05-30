#! /usr/bin/env python3


from pathlib import Path
import requests, json
from datetime import datetime
import subprocess
from typing import Tuple, List

BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)
MEMORY_TTL = 7 * 24 * 3600  # 7 days in seconds
MEMORY_TTL_ERASE = 30 * 24 * 3600  # 30 days in seconds


def save_memory(history, topic: str= "No topic"):
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
    filename = MEMORY_DIR / f"{timestamp}_{topic[:50].replace(' ', '_')}.md"
    with open(filename, "w") as f:
        for role, text in history:
            f.write(f"**{role}:** {text}\n\n")


def is_memory_file_to_load(file):
    if file.stem.startswith("init"):
        return True
    date_str = file.stem.split("_")[0]
    date = datetime.strptime(date_str, "%Y%m%d%H%M%S")
    if (datetime.now() - date).total_seconds() > MEMORY_TTL:
        if (datetime.now() - date).total_seconds() > MEMORY_TTL_ERASE:
            file.unlink()  # delete old memory file
        return False
    return True

from typing import List, Tuple

def load_memory() -> List[Tuple[str, str]]:
    """
    Load memory files from the MEMORY_DIR.
    Returns a list of tuples containing the role and text.
    """
    old_memories = []
    for file in MEMORY_DIR.glob("*.md"):
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

history = load_memory()
session_memory = []

def build_input_for_api(prompt: str) -> str:
    parts = []
    for role, text in history + session_memory:
        if role == "User":
            parts.append(f"User: {text}")
        else:
            parts.append(f"Assistant: {text}")
    parts.append(f"User: {prompt}")
    parts.append("Assistant:")
    return "\n".join(parts)

def process_prompt(prompt: str, display: bool = True) -> Tuple[List[Tuple[str, str]], str]:
    payload = {
        "model": "mistral",
        "prompt": build_input_for_api(prompt),
        "stream": True,
    }
    res = requests.post("http://localhost:11434/api/generate", json=payload, stream=True)

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
            output += piece

    session_memory.append(("User", prompt))
    session_memory.append(("Assistant", output))

    return session_memory, output
