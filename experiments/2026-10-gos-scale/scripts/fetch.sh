#!/bin/sh
# Download the GoS skills_500 library (MIT-licensed dataset) into ../data/
set -e
D="${GOS_DATA:-$(dirname "$0")/../data}"
mkdir -p "$D" && cd "$D"
curl -sL -o skills_500.tar.gz https://huggingface.co/datasets/davidliuk/graph-of-skills-data/resolve/main/skills_500.tar.gz
tar xzf skills_500.tar.gz 2>/dev/null
ls skills_500 | wc -l
# The 87 SkillsBench tasks (instruction.md + environment/skills/) go in tasks/ next to skills_500/.
