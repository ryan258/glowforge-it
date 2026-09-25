#!/usr/bin/env bash

# Run the Glowforge image prep CLI through uv, so you don't have to
# activate a virtual environment. Adds --clean-solids by default;
# pass --no-clean-solids to turn that off.
#
# This wrapper locates main.py but deliberately does NOT change directory.
# --input and -o stay relative to YOUR current working directory, so bare
# `gf` reads ./input and writes ./output wherever you are standing.
# Pass explicit paths when running from outside the repository.

# Get the directory where this script lives
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the python script with uv, passing along any extra arguments you provide
uv run "$DIR/main.py" --clean-solids "$@"
