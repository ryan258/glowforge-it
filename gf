#!/usr/bin/env bash

# Automatically process all images in the `input/` directory
# using the uv package manager so you don't have to activate
# the virtual environment. Defaults to --clean-solids.

# Get the directory where this script lives
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the python script with uv, passing along any extra arguments you provide
uv run "$DIR/main.py" --clean-solids "$@"
