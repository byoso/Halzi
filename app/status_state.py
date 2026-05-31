#! /usr/bin/env python3

import threading
from typing import Callable, Set

_lock = threading.Lock()
_status = "🟢 Ready"
_subscribers: Set[Callable[[str], None]] = set()


def get_status() -> str:
	with _lock:
		return _status


def set_status(text: str) -> None:
	global _status
	with _lock:
		_status = text
		subscribers = list(_subscribers)

	for callback in subscribers:
		try:
			callback(text)
		except Exception:
			# Status updates should never crash the app.
			pass


def subscribe(callback: Callable[[str], None], emit_current: bool = True) -> None:
	with _lock:
		_subscribers.add(callback)
		current = _status

	if emit_current:
		try:
			callback(current)
		except Exception:
			pass


def unsubscribe(callback: Callable[[str], None]) -> None:
	with _lock:
		_subscribers.discard(callback)
