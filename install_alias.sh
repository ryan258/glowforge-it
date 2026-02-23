#!/usr/bin/env bash

# This script adds a global alias for 'gf' to your ~/.zshrc file
# so you can run the Glowforge processor from anywhere.

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ALIAS_CMD="alias gf='$PROJECT_DIR/gf'"

# Check if the alias already exists
if grep -q "alias gf=" ~/.zshrc; then
    echo "'gf' alias already exists in ~/.zshrc."
    echo "If you need to update it, edit ~/.zshrc directly."
else
    echo "" >> ~/.zshrc
    echo "# Glowforge Image Processor" >> ~/.zshrc
    echo "$ALIAS_CMD" >> ~/.zshrc
    echo "Added 'gf' alias to ~/.zshrc!"
    echo "Run 'source ~/.zshrc' or open a new terminal tab to start using it."
fi
