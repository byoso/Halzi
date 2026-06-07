#! /bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

echo "$PARENT_DIR"

cd "$PARENT_DIR"

echo "Installing voice files in $(pwd)/piper/voices/"
# get onnx voice files for piper

# English voices
cd piper/voices/en/
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx.json

# French voices
cd ../fr/
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/upmc/medium/fr_FR-upmc-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/upmc/medium/fr_FR-upmc-medium.onnx.json

# personalities (default)
cd "$PARENT_DIR"
mkdir -p "$HOME/.local/share/geninstaller-applications/.data/halzimir/memory/personalities"
cp "$PARENT_DIR/memory/personalities/default.md" "$HOME/.local/share/geninstaller-applications/.data/halzimir/memory/personalities/default.md"