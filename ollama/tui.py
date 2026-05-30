
from typing import List, Tuple, Optional

from silly_engine.minuit import Menu, MenuItem
from silly_engine.text_tools import c
from core import (
    process_prompt,
    save_memory,
    MEMORY_DIR,
)
import subprocess
from pathlib import Path
import sys
import threading

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


def _close_conversation(history: Optional[List[Tuple[str, str]]] = None, save: bool = True) -> None:
    if history is None:
        history = []
    if save and history:
        _, topic = process_prompt("Answer with only 3 word to describe the topic of our last conversation:", display=False)
        save_memory(history, topic)
    main_menu.ask()


def tui_new_prompt(history: Optional[List[Tuple[str, str]]] = None) -> None:
    if history is None:
        history = []
    print("\n\njust press ENTER to exit")
    prompt = input(f"{c.green}Enter your prompt: {c.end}")
    print("\n")
    if prompt.strip() == "":
        _close_conversation(history)
        return
    history, _ = process_prompt(prompt)
    return tui_new_prompt(history)


def tui_voice_prompt(history: Optional[List[Tuple[str, str]]] = None) -> None:
    if history is None:
        history = []

    print("\n\nvoice mode active - press ENTER at any time to stop and save memory")

    try:
        from vad import load_vad, iter_voice_prompts
    except Exception as exc:
        print(f"{c.red}Voice mode unavailable: {exc}{c.end}")
        main_menu.ask()
        return

    stop_event = threading.Event()

    def wait_for_enter() -> None:
        input()
        stop_event.set()

    threading.Thread(target=wait_for_enter, daemon=True).start()

    try:
        vad_iterator = load_vad()
        for prompt in iter_voice_prompts(vad_iterator, stop_event=stop_event):
            if stop_event.is_set():
                break
            if not prompt.strip():
                continue
            print(f"\n{c.green}Prompt:{c.end} {prompt}\n")
            history, _ = process_prompt(prompt)
            print("\n")

            if stop_event.is_set():
                break

        _close_conversation(history, save=True)
        return
    except KeyboardInterrupt:
        print("\nLeaving voice mode without saving memory...")
        _close_conversation(history, save=False)
        return


def tui_memory() -> None:
    subprocess.run(["xdg-open", str(MEMORY_DIR)])
    main_menu.ask()




main_menu = Menu(
    items=[
        MenuItem("p", "prompt", tui_new_prompt),
        MenuItem("v", "voice", tui_voice_prompt),
        MenuItem("m", "memory", tui_memory),
        MenuItem("x", "exit", exit),
    ],
    width=80
)