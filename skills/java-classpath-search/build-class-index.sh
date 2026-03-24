#!/bin/bash
# Build an index of all classes in all Maven JARs for fast searching
# Output: tab-separated file with CLASS_PATH\tJAR_PATH

INDEX_FILE="${1:-$HOME/.cache/quarkusdev-skills/class-index.txt}"
REPO_DIR="${2:-$HOME/.m2/repository}"

# Ensure cache directory exists
mkdir -p "$(dirname "$INDEX_FILE")"

echo "Building class index from $REPO_DIR..." >&2

find "$REPO_DIR" -name "*.jar" \
  -not -name "*-sources*" \
  -not -name "*-javadoc*" \
  -not -name "*-tests*" \
  -not -name "*-test-*" | \
  xargs -P 8 -I{} sh -c '
    jar tf "$1" 2>/dev/null | grep "\.class$" | grep -v "module-info\|package-info" | while read cls; do
      printf "%s\t%s\n" "$cls" "$1"
    done
  ' _ {} > "$INDEX_FILE"

COUNT=$(wc -l < "$INDEX_FILE")
echo "Indexed $COUNT classes in $INDEX_FILE" >&2
