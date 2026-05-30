#!/usr/bin/env python3


from silly_engine.router import Router
from silly_engine.text_tools import c, print_title
from tui import main_menu

def cli_run():
    print_title("Ollama AI Assistant", color=c.cyan, step=2)
    main_menu.ask()


router = Router("AI Assistant (Ollama)")

router.add_routes([
    (["", "-h", "--help"], router.display_help, "Show this help message"),
    ("run", cli_run, "Run the AI assistant")
    ]
)


if __name__ == "__main__":
    try:
        router.query()
    except KeyboardInterrupt:
        print("\nExiting...")