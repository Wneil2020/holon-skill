#!/bin/sh
# Download the GoS skills_1000 library (MIT-licensed dataset) into ../data/
set -e
D="${GOS_DATA:-$(dirname "$0")/../data}"
mkdir -p "$D" && cd "$D"
curl -sL -o skills_1000.tar.gz https://huggingface.co/datasets/davidliuk/graph-of-skills-data/resolve/main/skills_1000.tar.gz
tar xzf skills_1000.tar.gz 2>/dev/null
ls skills_1000 | wc -l
