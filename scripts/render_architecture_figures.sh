#!/usr/bin/env bash

set -euo pipefail

figure_dir="docs/figures/architecture"

if [ ! -d "$figure_dir" ]; then
  echo "Missing figure directory: $figure_dir" >&2
  exit 1
fi

if command -v mmdc >/dev/null 2>&1; then
  renderer=(mmdc)
  echo "Using local Mermaid CLI: $(command -v mmdc)"
else
  renderer=(npx -y @mermaid-js/mermaid-cli)
  echo "Using Mermaid CLI through npx."
fi

shopt -s nullglob
mmd_files=("$figure_dir"/*.mmd)

if [ "${#mmd_files[@]}" -eq 0 ]; then
  echo "No Mermaid source files found in $figure_dir" >&2
  exit 1
fi

echo "Rendering Mermaid figures..."
for source_file in "${mmd_files[@]}"; do
  output_file="${source_file%.mmd}.svg"
  echo "  Rendering $source_file -> $output_file"
  "${renderer[@]}" -i "$source_file" -o "$output_file" --backgroundColor white
done

echo "Rendered ${#mmd_files[@]} architecture figure(s)."
