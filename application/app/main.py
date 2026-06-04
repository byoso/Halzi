#! /usr/bin/env python3

"""
This is the main entry point for the Halzimir application.
"""
import sys
from pathlib import Path

# When running this script from the `app/` directory, ensure the project root
# (parent of `app/`) is on `sys.path` so `app` package imports resolve.
ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

from app.core import ensure_ollama_running
from app.gui.error_dialogue import show_error_dialog
from app.gui.main_gui import MainWindow
from app.database.db import init_db

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk


if __name__ == "__main__":
    try:
        # database initialization (creates tables and default settings if not exist)
        init_db()
        # Ensure Ollama model/server is running before starting voice activity detection
        ok = ensure_ollama_running()
        if not ok:
            msg = "Ollama is not available and could not be started. Exiting."
            show_error_dialog(msg, title="Ollama Error")
            sys.exit(1)

        # Launch GUI (GTK main loop must run in main thread)
        window = MainWindow()
        # Note: VAD is started on-demand by the UI (CenterPanel.start_voice_input)
        # to avoid opening multiple simultaneous audio input streams.
        window.show_all()
        gtk.main()
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")