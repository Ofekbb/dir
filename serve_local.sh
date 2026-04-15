#!/usr/bin/env bash
set -e
DIR=$(mktemp -d)
cp -r frontend/* "$DIR/"
mkdir -p "$DIR/data"
cp data/apartments.json "$DIR/data/" 2>/dev/null || echo '[]' > "$DIR/data/apartments.json"
echo "Dashboard: http://localhost:8080"
cd "$DIR" && python3 -m http.server 8080
