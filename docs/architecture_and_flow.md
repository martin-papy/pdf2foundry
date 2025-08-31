# High-level system design

1. **Inputs**

   - One PDF (born-digital, selectable text).
   - Optional CLI flags (see below).

1. **Outputs**

   - An **installable module folder** containing:

     - `module.json` (declares a **Journal** compendium pack; no dependency needed for v13 folders).
     - `assets/` (images extracted from the PDF, unchanged).
     - `styles/pdf2foundry.css` (scoped, non-conflicting CSS).
     - `sources/journals/*.json` (source JSON for Journal Entries).
     - `packs/<pack-name>/` (LevelDB pack produced by compile step).

   - Optional: a “TOC” Journal Entry with clickable `@UUID[...]` links.

1. **Core Foundry facts used**

   - Journal Page **HTML format** is supported in v12 via `JOURNAL_ENTRY_PAGE_FORMATS.HTML`. ([Foundry Virtual Tabletop][1])
   - Journals & Pages are proper Documents; we can rely on UUID linking (`@UUID[...]`) and the journal/page document models. ([Foundry Virtual Tabletop][2], [Foundry VTT Wiki][3])
   - Since v11, compendium packs are **LevelDB directories**; build packs using the **official packaging flow** (Module Maker or CLI). ([Foundry Virtual Tabletop][4])
   - v13 supports native **folders inside packs**; no external dependency required.

______________________________________________________________________

## CLI UX (first pass)

```bash
pdf2foundry \
  --pdf "My Book.pdf" \
  --mod-id "pdf2foundry-my-book" \
  --mod-title "My Book (PDF Import)" \
  --author "ACME" \
  --license "OGL" \
  --pack-name "my-book-journals" \
  --root-folder "My Book" \
  --toc yes \
  --tables auto \            # auto | image-only
  --images-dir assets \
  --out-dir ./dist \
  --deterministic-ids yes
```

Defaults aim for “happy path”; flags keep room for future growth.

______________________________________________________________________

## Processing pipeline

### Module size and boundaries

- Keep each Python module focused; avoid files larger than ~500 lines.
- If a file approaches the limit, split into cohesive submodules under the same package (e.g., `parser/outline.py`, `parser/content.py`, `parser/images.py`).
- Prefer narrow, typed protocols and dataclasses at boundaries to keep modules decoupled.
- Enforced by pre-commit hook `scripts/check_file_length.py` and CI.

1. **Parse PDF → logical tree**

   - Library: **Docling** for extracting structured HTML, images, tables, links, and headings/bookmarks (primary driver for chapters).
   - When bookmarks are absent, rely on Docling's heading detection to derive sections.
   - Multi-column pages: **flatten** into linear order (your preference).
   - Output: an in-memory tree: `Book → Chapters → Sections (with flow blocks, images, links, table candidates)`.

1. **Tables**

   - Use Docling's table recognition to produce real `<table>` HTML when available.
   - If low confidence or absent: rasterize that region to an image and embed.

1. **Images**

   - Extract **as-is** (original resolution/format) into `assets/`.
   - Track mapping `pdfObjectId → moduleRelativePath`.

1. **HTML page generation**

   - Build clean, semantic HTML (h1–h4, p, ul/ol, table, figure/figcaption, img, code/pre where relevant).
   - Add **anchor ids** for section headings to aid intra-entry linking.
   - Keep markup within Foundry’s supported **HTML page format**; avoid script; keep CSS minimal & **scoped** under a wrapper like `<div class="pdf2foundry">…</div>`. ([Foundry Virtual Tabletop][1])

1. **Internal link resolution**

   - **Real PDF link annotations**: map target page/rect to owning Chapter/Section → build `@UUID[JournalEntry.<E>.JournalEntryPage.<P>]{label}`.
   - **Plain-text cross-refs** (“see Chapter 3”, “§2.4”): regex pass to resolve to known sections when unambiguous; otherwise leave plain text.
   - External links: normal `<a href="...">`.

1. **Deterministic IDs**

   - `_id = sha1(<mod-id>|<chapter-key>|<section-key>)[:16]` for JournalEntries and JournalPages.
   - This ensures **stable UUIDs across re-runs** so links don’t break. (Foundry’s runtime will form document UUIDs that include these IDs.) ([Foundry VTT Wiki][3])

1. **Foundry source JSON modeling (per Journal Entry)**

   - One **Journal Entry = one Chapter**.

   - Each **Section = one Journal Page** (`type: "text"`, `text.format: "html"`; page `name`, `sort`, `image?` if needed).

   - Optional **folders inside pack**: flags may be included for compatibility; v13 reads native folders.

   - Example (trimmed):

     ```json
     {
       "_id": "a1b2c3d4e5f6a7b8",
       "name": "Chapter 1 — Introduction",
       "pages": [
         {
           "_id": "p111222333444555",
           "name": "Overview",
           "type": "text",
           "text": { "format": 1, "content": "<div class='pdf2foundry'><h2>…</h2>…</div>" },
           "sort": 100
         }
       ]
     }
     ```

     Where `text.format: 1` corresponds to **HTML** in v12. ([Foundry Virtual Tabletop][1])

1. **TOC generation (optional)**

   - Create a “Table of Contents” Journal Entry with a page of links like:
     `@UUID[JournalEntry.<ch-id>.JournalEntryPage.<sec-id>]{Chapter 1: Overview}`.
   - Users can click through directly in Foundry. ([Foundry Virtual Tabletop][7])

1. **Packaging → installable compendium**

   - Create module skeleton:

     ```text
     module.json
     packs/<pack-name>/      # LevelDB output (after compile)
     sources/journals/*.json # our entry sources
     assets/...
     styles/pdf2foundry.css
     ```

   - `module.json` essentials:

     - `id`, `title`, `version`, `compatibility` (v13+), `authors`, `packs` (type: `"JournalEntry"`). ([Foundry Virtual Tabletop][8])

   - **Compile packs** from `sources/` to `packs/` using the **official packaging route** (recommended since v11). You can do this via the **Module Maker UI** or its CLI-equivalent flow; either way, the result is a proper **LevelDB pack**. ([Foundry Virtual Tabletop][9])

______________________________________________________________________

## Directory layout (result)

```text
dist/
  pdf2foundry-my-book/
    module.json
    assets/
      img_0001.png
      ...
    styles/
      pdf2foundry.css
    sources/
      journals/
        ch01.json
        ch02.json
        toc.json
    packs/
      my-book-journals/   # LevelDB pack after compile
```

______________________________________________________________________

## Error handling & reporting

- **Missing bookmarks / ambiguous structure** → fall back to heading heuristic; log a summary report (chapters/sections detected, unresolved refs).
- **Table extraction fails** → image fallback, with a note in the report.
- **Broken internal reference** → leave as plain text and note in the report.
- **Images** → if extraction fails for any object, rasterize the region from the page as a last resort.

______________________________________________________________________

## Validation checklist (done post-build in a v12 world)

1. Install the module; verify the **Journal pack** appears and imports. ([Foundry Virtual Tabletop][8])
1. Open a few pages: confirm **HTML rendering** and assets load. ([Foundry Virtual Tabletop][10])
1. Click TOC links: confirm **UUID navigation** to pages. ([Foundry Virtual Tabletop][7])
1. v13 native pack folders present as expected.

______________________________________________________________________

## What’s next (implementation order)

1. Minimal parser (bookmarks → chapters; sections by heading heuristic) + HTML generator + image export.
1. JSON emit for Journal Entries/Pages + **deterministic IDs** + TOC.
1. Packaging step (compile pack) and runtime verification in v12. ([Foundry Virtual Tabletop][4])
1. Refine table extraction (Docling options) + internal link mapping (annotations + regex).
1. Optional polish: scoped CSS, edge-case heuristics, CLI ergonomics.

______________________________________________________________________

If this matches your expectations, I’ll draft the **Journal Entry/Page JSON schema** we’ll emit (field-by-field, v12-safe), plus a **sample `module.json`** and the exact **build command(s)** we’ll run from the CLI.

[1]: https://foundryvtt.com/api/v12/enums/foundry.CONST.JOURNAL_ENTRY_PAGE_FORMATS.html?utm_source=chatgpt.com "JOURNAL_ENTRY_PAGE_FORMATS | Foundry Virtual Tabletop - API ..."
[2]: https://foundryvtt.com/api/v12/classes/client.JournalEntryPage.html?utm_source=chatgpt.com "JournalEntryPage | Foundry Virtual Tabletop - API Documentation ..."
[3]: https://foundryvtt.wiki/en/development/api/document?utm_source=chatgpt.com "Document | Foundry VTT Community Wiki"
[4]: https://foundryvtt.com/article/v11-leveldb-packs/?utm_source=chatgpt.com "Version 11 Content Packaging Changes - Foundry Virtual Tabletop"
[7]: https://foundryvtt.com/article/journal/?utm_source=chatgpt.com "Journal Entries - Foundry Virtual Tabletop"
[8]: https://foundryvtt.com/article/compendium/?utm_source=chatgpt.com "Compendium Packs - Foundry Virtual Tabletop"
[9]: https://foundryvtt.com/article/packaging-guide/?utm_source=chatgpt.com "Content Packaging Guide - Foundry Virtual Tabletop"
[10]: https://foundryvtt.com/api/v12/classes/client.JournalPageSheet.html?utm_source=chatgpt.com "JournalPageSheet | Foundry Virtual Tabletop - API Documentation ..."
