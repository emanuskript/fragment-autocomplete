# Architecture Build Notes

## Dependencies

Figure rendering uses Mermaid CLI. The render script first checks for a local `mmdc` executable. If it is unavailable, it uses:

```bash
npx -y @mermaid-js/mermaid-cli
```

PDF generation prefers `pandoc` with an available PDF engine such as `xelatex`, `lualatex`, `pdflatex`, `tectonic`, or `wkhtmltopdf`.

If `pandoc` or a PDF engine is unavailable, the build script tries a Node-based Markdown-to-PDF fallback:

```bash
npx -y md-to-pdf
```

If PDF generation still fails, the script generates an HTML fallback at:

```text
outputs/Fragment_Autocomplete_Architecture_Draft.html
```

## Render Figures

```bash
bash scripts/render_architecture_figures.sh
```

This renders all Mermaid files in `docs/figures/architecture/` to SVG files in the same directory.

## Build PDF

```bash
bash scripts/build_architecture_pdf.sh
```

The script always renders figures first, then builds:

```text
outputs/Fragment_Autocomplete_Architecture_Draft.pdf
```

If PDF generation is not possible, it creates:

```text
outputs/Fragment_Autocomplete_Architecture_Draft.html
```

## Validate Workspace

```bash
bash scripts/check_workspace.sh
```

The validation script checks required folders, documents, Mermaid sources, rendered SVGs, build scripts, and the final PDF or HTML fallback.

## Troubleshooting

- If Mermaid rendering fails, install Node.js/npm or install Mermaid CLI globally with `npm install -g @mermaid-js/mermaid-cli`.
- If `npx` cannot download packages, check network access.
- If Pandoc PDF export fails, install Pandoc and a LaTeX engine such as TeX Live with XeLaTeX.
- If Chrome/Chromium sandbox errors appear during Node-based PDF export, use the HTML fallback or install a local browser and PDF engine.
