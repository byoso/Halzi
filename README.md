# Project Halzimir (WIP)

Halzimir is a local AI interface to make the use of a LLM convenient and efficient, as simple to use as the online ones, the only limit is the power of the PC.


# Installation

## Step 1 - Install Ollama

```sh
curl -fsSL https://ollama.com/install.sh | sh
```
[Ollama Home Page](https://ollama.com/download)

Ollama is some kind of a "docker" service, in wich you can run models (quite like docker images)

You need at least one of ollama's AI model to run Halzimir, so let's pick a light one to begin with:

```bash
ollama pull qwen2.5-coder:1.5b-base
```


## Step 2 - Install Halzimir

```bash
sudo apt install pipx  #  if not already installed

pipx install geninstaller

# then go in the Halzimir/application directory and run
./installer

# if something is missing the installer will probably tell you what to do.
```
Once the installation done, you'll find Halzimir in the category "Development" of your apps.

# Talk time about Ollama models

Once Ollama is installed, adding a model is as simple as:
```
ollama pull <model name>

e.g:
ollama pull llama3.1:8b

```

So far I've tried a few, let me sum my experiments (just my point of view):

| Model name | My feeling |
| --- | --- |
| llama3.1:8b-instruct-q3_K_L | Very fast, not too dumb, but not accurate enought for me |
| qwen2.5-coder:1.5b-base | fast , not accurate enought |
| qwen3:8b | for me the best compromise, at the limit of my PC and accurate enought to work with |
| qwen3:14b | Way too heavy for my PC, maybe it could be worth trying a 3 bit version if it exists |
| mistral:7B | Definitly not good for my usage |
| llama3.1:8b | my other favorite with qwen3:8b, I balance between this 2 |
