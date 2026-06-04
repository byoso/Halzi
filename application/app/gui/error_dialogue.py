#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk

from app.gui.logger import logger


def show_error_dialog(message: str, title: str = "Error") -> None:
    """Show a simple modal error dialog with the provided message.

    This function blocks until the user closes the dialog.
    """
    try:
        dialog = gtk.MessageDialog(
            transient_for=None,
            flags=0,
            type=gtk.MessageType.ERROR,
            buttons=gtk.ButtonsType.OK,
            message_format=message,
        )
        dialog.set_title(title)
        dialog.run()
        dialog.destroy()
    except Exception as exc:
        # Fallback to logging if GTK is unavailable
        logger.error(f"{title}: {message} (GUI unavailable: {exc})")

if __name__ == "__main__":
    # Test the error dialog
    show_error_dialog("This is a test error message.", title="Test Error")