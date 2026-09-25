#!/usr/bin/env bash

# This script adds a global alias for 'gf' to your ~/.zshrc file
# so you can run the Glowforge processor from anywhere.
#
# zsh only. For bash or fish, add the equivalent alias to your own profile:
#   alias gf='<repo>/gf'
# The alias does not change directory: see the note in ./gf and the README.

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ALIAS_CMD="alias gf='$PROJECT_DIR/gf'"

# Check if the alias already exists
if [ ! -f ~/.zshrc ] && [ "$(basename "${SHELL:-}")" != "zsh" ]; then
    echo "No ~/.zshrc found and your shell is not zsh."
    echo "Add this line to your shell profile instead:"
    echo "  $ALIAS_CMD"
    exit 1
fi

if grep -q "alias gf=" ~/.zshrc 2>/dev/null; then
    echo "'gf' alias already exists in ~/.zshrc."
    echo "If you need to update it, edit ~/.zshrc directly."
else
    echo "" >> ~/.zshrc
    echo "# Glowforge Image Processor" >> ~/.zshrc
    echo "$ALIAS_CMD" >> ~/.zshrc
    echo "Added 'gf' alias to ~/.zshrc!"
    echo "Run 'source ~/.zshrc' or open a new terminal tab to start using it."
fi
