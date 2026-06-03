#! /bin/env bash

app_name="Halzimir"


echo "Performing some checks before installing $app_name..."
echo ""
echo "$app_name requires the following dependencies:"
echo "  - wget (to download Piper voice files)"
echo "  - Ollama (to run LLM models)"
echo "  - At least one Ollama model must be installed"
echo ""


if ! command -v wget >/dev/null 2>&1; then
    echo "🛑 Aborted !: wget is required to download Piper voice files."
    echo ""
    echo "Please install wget first and run this installer script again."
    echo "Example (Debian/Ubuntu/linux Mint):"
    echo "  sudo apt update"
    echo "  sudo apt install wget"
    exit 1
else
    echo "wget is installed. ✅"
    echo ""
fi


if ! command -v ollama >/dev/null 2>&1; then
    echo "🛑 Aborted !: Ollama is required to run $app_name."
    echo ""
    echo "Please install Ollama first and run this installer script again."
    echo "See: https://ollama.com/download"
    exit 1
else
    echo "Ollama is installed. ✅"
    echo ""
fi


if [ "$(ollama list 2>/dev/null | wc -l)" -le 1 ]; then
    echo "🛑 Aborted !: No Ollama models were found."
    echo ""
    echo "Please download at least one model before installing $app_name."
    echo "Example:"
    echo "  ollama pull mistral"
    exit 1
else
    echo "Ollama models found. ✅"
    echo ""
fi
