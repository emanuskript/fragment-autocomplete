#!/usr/bin/env bash

set -euo pipefail

doc="docs/01_architecture_overview.md"
out_dir="outputs"
pdf="$out_dir/Fragment_Autocomplete_Architecture_Draft.pdf"
html="$out_dir/Fragment_Autocomplete_Architecture_Draft.html"

mkdir -p "$out_dir"

if [ ! -f "$doc" ]; then
  echo "Missing architecture document: $doc" >&2
  exit 1
fi

echo "Rendering figures before document export..."
bash scripts/render_architecture_figures.sh

rm -f "$pdf" "$html"

build_pdf_with_pandoc() {
  local engines=()

  for engine in xelatex lualatex pdflatex tectonic wkhtmltopdf; do
    if command -v "$engine" >/dev/null 2>&1; then
      engines+=("$engine")
    fi
  done

  if ! command -v pandoc >/dev/null 2>&1; then
    echo "Pandoc is not installed; skipping Pandoc PDF build."
    return 1
  fi

  if [ "${#engines[@]}" -eq 0 ]; then
    echo "Pandoc is installed, but no PDF engine was found."
    return 1
  fi

  for engine in "${engines[@]}"; do
    echo "Trying Pandoc PDF build with $engine..."
    if pandoc "$doc" \
      -o "$pdf" \
      --from markdown \
      --pdf-engine="$engine" \
      -V geometry:margin=1in \
      -V fontsize=11pt \
      --toc; then
      echo "PDF generated: $pdf"
      return 0
    fi
  done

  echo "Pandoc PDF build failed with all available engines."
  return 1
}

build_pdf_with_node() {
  if ! command -v npx >/dev/null 2>&1; then
    echo "npx is not available; skipping Node-based PDF fallback."
    return 1
  fi

  echo "Trying Node-based PDF build with md-to-pdf..."
  local temp_pdf="${doc%.md}.pdf"
  rm -f "$temp_pdf"
  if npx -y md-to-pdf "$doc" \
    --basedir docs \
    --pdf-options '{"format":"A4","margin":{"top":"1in","right":"1in","bottom":"1in","left":"1in"},"printBackground":true}'; then
    if [ -f "$temp_pdf" ]; then
      mv "$temp_pdf" "$pdf"
    fi
  fi

  if [ -f "$pdf" ]; then
    echo "PDF generated: $pdf"
    return 0
  fi

  echo "Node-based PDF build failed."
  return 1
}

build_html_fallback() {
  echo "Generating HTML fallback: $html"
  node - "$doc" "$html" <<'NODE'
const fs = require("fs");
const path = require("path");

const input = process.argv[2];
const output = process.argv[3];
const markdown = fs.readFileSync(input, "utf8");

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function inline(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function renderTable(lines) {
  const rows = lines
    .filter((line) => line.trim().startsWith("|"))
    .map((line) => line.trim().slice(1, -1).split("|").map((cell) => inline(cell.trim())));
  if (rows.length < 2) return "";
  const header = rows[0].map((cell) => `<th>${cell}</th>`).join("");
  const body = rows.slice(2).map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("\n");
  return `<table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`;
}

const lines = markdown.split(/\r?\n/);
const htmlParts = [];
let i = 0;

while (i < lines.length) {
  const line = lines[i];
  const trimmed = line.trim();

  if (!trimmed) {
    i += 1;
    continue;
  }

  if (trimmed.startsWith("```")) {
    const lang = trimmed.slice(3).trim();
    const block = [];
    i += 1;
    while (i < lines.length && !lines[i].trim().startsWith("```")) {
      block.push(lines[i]);
      i += 1;
    }
    i += 1;
    htmlParts.push(`<pre><code class="language-${escapeHtml(lang)}">${escapeHtml(block.join("\n"))}</code></pre>`);
    continue;
  }

  if (trimmed.startsWith("|")) {
    const table = [];
    while (i < lines.length && lines[i].trim().startsWith("|")) {
      table.push(lines[i]);
      i += 1;
    }
    htmlParts.push(renderTable(table));
    continue;
  }

  const imageMatch = trimmed.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
  if (imageMatch) {
    const alt = escapeHtml(imageMatch[1]);
    const src = escapeHtml(imageMatch[2]);
    htmlParts.push(`<figure><img src="../docs/${src}" alt="${alt}"><figcaption>${alt}</figcaption></figure>`);
    i += 1;
    continue;
  }

  const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
  if (heading) {
    const level = heading[1].length;
    htmlParts.push(`<h${level}>${inline(heading[2])}</h${level}>`);
    i += 1;
    continue;
  }

  if (trimmed.startsWith("- ")) {
    const items = [];
    while (i < lines.length && lines[i].trim().startsWith("- ")) {
      items.push(`<li>${inline(lines[i].trim().slice(2))}</li>`);
      i += 1;
    }
    htmlParts.push(`<ul>${items.join("\n")}</ul>`);
    continue;
  }

  const paragraph = [trimmed];
  i += 1;
  while (
    i < lines.length &&
    lines[i].trim() &&
    !lines[i].trim().startsWith("#") &&
    !lines[i].trim().startsWith("- ") &&
    !lines[i].trim().startsWith("|") &&
    !lines[i].trim().startsWith("```") &&
    !lines[i].trim().startsWith("![")
  ) {
    paragraph.push(lines[i].trim());
    i += 1;
  }
  htmlParts.push(`<p>${inline(paragraph.join(" "))}</p>`);
}

const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fragment Autocomplete Architecture Draft</title>
  <style>
    body {
      color: #1f2933;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 16px;
      line-height: 1.6;
      margin: 0 auto;
      max-width: 980px;
      padding: 48px 32px;
    }
    h1, h2, h3 { color: #0f1720; line-height: 1.25; }
    h1 { font-size: 34px; border-bottom: 2px solid #d5d9df; padding-bottom: 14px; }
    h2 { margin-top: 36px; font-size: 24px; }
    code { background: #eef2f5; border-radius: 4px; padding: 1px 4px; }
    pre { background: #f4f6f8; border: 1px solid #d5d9df; overflow-x: auto; padding: 14px; }
    table { border-collapse: collapse; font-size: 14px; margin: 20px 0; width: 100%; }
    th, td { border: 1px solid #d5d9df; padding: 8px; text-align: left; vertical-align: top; }
    th { background: #eef2f5; }
    figure { margin: 28px 0; }
    figcaption { color: #5d6876; font-size: 14px; margin-top: 8px; }
    img { border: 1px solid #d5d9df; max-width: 100%; }
    @media print {
      body { max-width: none; padding: 24px; }
      h2 { break-before: auto; }
      figure, table { break-inside: avoid; }
    }
  </style>
</head>
<body>
${htmlParts.join("\n")}
</body>
</html>
`;

fs.writeFileSync(output, html);
NODE
  echo "HTML fallback generated: $html"
}

if build_pdf_with_pandoc; then
  exit 0
fi

if build_pdf_with_node; then
  exit 0
fi

echo "PDF generation failed because Pandoc/PDF-engine or Node browser dependencies are unavailable."
build_html_fallback
