#! /usr/bin/env python3

"""
This is the main entry point for the Jarvis application.
"""
from vad import main as vad_main




if __name__ == "__main__":
    try:
        vad_main()
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")