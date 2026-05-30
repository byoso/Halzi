
from typing import List, Tuple, Optional

from silly_engine.minuit import Menu, MenuItem
from silly_engine.text_tools import c
from core import (
    process_prompt,
    save_memory,
    MEMORY_DIR,
)
import subprocess


def tui_new_prompt(history: Optional[List[Tuple[str, str]]] = None) -> None:
    if history is None:
        history = []
    print("\n\njust press ENTER to exit")
    prompt = input(f"{c.green}Enter your prompt: {c.end}")
    print("\n")
    if prompt.strip() == "":
        _, topic = process_prompt("Answer with only 3 word to describe the topic of our last conversation:", display=False)
        save_memory(history, topic)
        main_menu.ask()
        return
    history, _ = process_prompt(prompt)
    return tui_new_prompt(history)


def tui_memory() -> None:
    subprocess.run(["xdg-open", str(MEMORY_DIR)])
    main_menu.ask()




main_menu = Menu(
    items=[
        MenuItem("p", "prompt", tui_new_prompt),
        MenuItem("m", "memory", tui_memory),
        MenuItem("x", "exit", exit),
    ],
    width=80
)