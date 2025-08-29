# Technical Feasibility Analysis

## 1) Is it technically possible?

**Yes.** All core primitives exist in v12+: Journal Entries contain **Journal Pages** whose **format can be HTML**; Journals support internal **UUID links**; and v11+ compendia use **LevelDB packs** that can be built from JSON/YAML using the **official Foundry CLI** (so we don’t have to hand-roll the DB format). ([DeepWiki][1], [Foundry Virtual Tabletop][2], [GitHub][3], [npm][4])

______________________________________________________________________

## 2) Foundry VTT compatibility surface (v12+)

- **Journal Entries & Pages**

  - Journal Entries are containers of **Pages**; editing supports raw **HTML** (or Markdown). For our “layout-ish” goal, we’ll generate HTML pages. ([Foundry Virtual Tabletop][5])

- **Document/UUID linking**

  - Documents have stable **UUIDs**; the journal UI supports **dynamic links** using `@UUID[...]`. We can prebuild links across our generated entries/pages. ([Foundry Virtual Tabletop][6])

- **Compendium packs**

  - Since **v11**, packs are **LevelDB directories** (not a single `.db` text file). Use the **official Foundry CLI** to compile JSON/YAML sources into packs. ([Foundry Virtual Tabletop][7], [GitHub][3], [npm][4])

- **Compendium organization / folders**

  - Core Foundry offers folders for packs in the sidebar; “folders **inside** packs” require the **Compendium Folders** add-on, which we can declare as a dependency. ([Foundry Virtual Tabletop][8], [GitHub][9])

**Conclusion:** Everything we need is supported natively in v12+ (plus an optional dependency for inner-pack folders).

______________________________________________________________________

## 3) Proposed end-to-end pipeline (Python CLI)

1. **PDF ingest (born-digital only)**

   - Library: **Docling** (and `docling-core`) to derive structured HTML (headings, paragraphs, lists), images, tables, and links from the PDF; use **Pillow** for rasterization fallback where needed.

   - Output: a **logical document tree** (Book → Chapters → Sections) with:

     - Cleaned **HTML** per Section (see §4),
     - Extracted **images** saved as files,
     - **Tables**: try real `<table>` when detected; otherwise rasterize the region and treat it as an image (meets your “try tables, else image” rule).

1. **Structure building**

   - **Chapters** primarily from **PDF bookmarks**; fallback to **font-size/weight** + heading heuristics when no bookmarks exist.
   - Flatten multi-column into a single reading order (your chosen simplification).

1. **Link resolution**

   - **Internal links**:

     - If the PDF has real intra-document link annotations, map targets to our Chapter/Page nodes.
     - If cross-refs are plain text (e.g., “see Chapter 3”), apply regex heuristics to auto-link to the target node when unambiguous.

   - **External links**: keep them as `<a href>`.

1. **Foundry document modeling (JSON)**

   - For each **Chapter ⇒ one Journal Entry**.
   - For each **important Section ⇒ one Journal Page** of **format=HTML** with our generated HTML content.
   - Assign **deterministic `_id`s** (e.g., `sha1(<pdfPath>|<chapterPath>|<sectionPath>)[:16]`) so that inter-page `@UUID` links are stable across re-runs.
   - Conform to **v12 JournalEntryData / JournalEntryPageData** fields (`_id`, `name`, `pages[]`, `folder`, `ownership`, `flags`, etc.). ([Foundry Virtual Tabletop][2])

1. **Assets**

   - Export images **as-is** to a module `assets/` folder; reference them in HTML via module-relative paths.

1. **Packaging to an installable compendium**

   - Create a minimal **module folder** with `module.json` (`packs`, `dependencies` incl. **Compendium Folders**), `assets/`, optional `styles/`.
   - Author sources as **JSON or YAML files** (one file per **Journal Entry**).
   - Use **Foundry’s official CLI (@foundryvtt/foundryvtt-cli)** `compilePack()` to build **LevelDB packs** under `packs/`. This is the supported, future-proof path for v11+. ([GitHub][3], [npm][4], [Foundry Virtual Tabletop][7])
   - Result: a normal **installable module** containing the compendium(s); GMs can import entries into a world (“Import All”) and, if installed, see the **inner folders** via Compendium Folders. ([Foundry VTT Wiki][10])

1. **Optional:** generate a **TOC Journal Entry** with HTML links to every Chapter/Section via `@UUID[JournalEntry.<id>.JournalEntryPage.<id>]`.

______________________________________________________________________

## 4) HTML generation constraints (v12+)

- **HTML page format** is officially supported for Journal Pages in v12. We’ll keep markup **semantically clean** (headings, lists, tables, images, anchors). ([Foundry Virtual Tabletop][11])
- **Styling**: ship a small **scoped CSS** in the module (e.g., `.pdf2foundry` namespace) to improve spacing, callouts, float images, etc., without conflicting with Foundry core styles.
- **Safety knobs**: avoid inline JS; constrain CSS to journals only.

______________________________________________________________________

## 5) Handling images, tables, and vector art

- **Images**: extracted and saved **unchanged**; journal HTML uses `<img src="modules/<mod-id>/assets/...">`.

- **Tables**:

  - Use **Docling's** table recognition to reconstruct real `<table>` → better UX, searchable.
  - If detection fails or the table is really artwork: **rasterize** the table region and insert an `<img>`.

- **Other vector graphics (diagrams, icons)**: rasterize to PNG at an appropriate DPI (configurable later).

- **Performance**: Since we’re keeping images “as-is,” we’ll warn users if the asset folder is very large, but we won’t compress (per requirements).

______________________________________________________________________

## 6) Foldering / hierarchy

- **Root folder per PDF** and **Chapter folders within** the compendium: this **requires “Compendium Folders”** for inner-pack folders; we’ll declare it in `module.json` dependencies. Without the add-on, the structure can still be **encoded in names** and a TOC. ([Foundry Virtual Tabletop][12], [GitHub][9])

______________________________________________________________________

## 7) Deterministic IDs & internal links

- We’ll generate `_id`s from stable hashes so **UUIDs don’t change** between runs; then build `@UUID[...]` strings for cross-refs and the TOC.
- Journals support **prose editor UUID links**, and the **Document API** exposes each document’s `uuid`. We’re writing source JSON with our `_id`s; once packed, the **UUIDs are stable** (scope: inside the compendium/module). ([Foundry Virtual Tabletop][6])

______________________________________________________________________

## 8) Packaging path (what we actually ship)

- **Module layout** (example):

  ```text
  module.json
  packs/
    pdf-name-journals/    ← LevelDB directory after packing
  assets/
    <images from pdf>...
  styles/
    pdf2foundry.css
  sources/
    journals/
      <journal-entry-1>.json
      <journal-entry-2>.json
      ...
  ```

- Build step: use **foundryvtt-cli** to **compile** `sources/journals/*.json` → `packs/pdf-name-journals`. This is the officially supported way to create LevelDB compendia from JSON. ([GitHub][3], [npm][4])

______________________________________________________________________

## 9) Risks & mitigations

1. **Complex layouts** (multi-column, sidebars, floating callouts)

   - *Mitigation*: linearize reading order; preserve images; add gentle CSS for callouts; revisit advanced layout later.

1. **Table detection isn’t perfect**

   - *Mitigation*: if parsing confidence is low, fall back to image; allow a CLI flag (`--tables=auto|image-only`) later.

1. **Pack format fragility**

   - v11+ uses **LevelDB**; do **not** hand-write DB files. Always use the **official Foundry CLI** (actively maintained). ([Foundry Virtual Tabletop][7], [GitHub][3])

1. **Compendium inner folders are non-core**

   - *Mitigation*: hard-depend on **Compendium Folders**; otherwise, encode hierarchy via names/TOC. ([Foundry Virtual Tabletop][12])

1. **HTML sanitization & future editor changes**

   - *Mitigation*: keep markup simple, avoid exotic tags/styles, and lean on the **HTML format** supported by v12. ([Foundry Virtual Tabletop][11])

______________________________________________________________________

## 10) Proof-of-Concept plan (1–2 iterations)

**PoC-1 (happy path, no OCR):**

- Parse a sample PDF with bookmarks and a few images/tables.

- Produce:

  - 1 **compendium module** with 1 **Journal pack**,
  - 1 **Journal Entry per Chapter**, **HTML Pages per Section**,
  - Images exported to `assets/`,
  - Deterministic IDs,
  - A **TOC** entry with working `@UUID` links.

- Compile with **foundryvtt-cli** and install in a v12 world; verify rendering and navigation. ([npm][4])

**PoC-2 (edge cases):**

- Refine Docling table recognition and settings, auto-linker for “see Chapter …”, handle external links, validate with/without Compendium Folders enabled. ([Foundry Virtual Tabletop][12])

______________________________________________________________________

## 11) Libraries & tooling (initial picks)

- **Python**: Docling, docling-core, Pillow (image ops, if needed), Jinja2 (HTML templating).
- **Packing**: **@foundryvtt/foundryvtt-cli** (Node) invoked from Python (subprocess). ([npm][4])
- **Foundry refs**: Journal docs & page formats, UUID links, compendium guides, LevelDB change notes. ([Foundry Virtual Tabletop][5])

______________________________________________________________________

## 12) Feasibility verdict

- **Technically feasible now**, using stable, supported APIs and the **official pack compiler**.
- **Scope constraints** you set (born-digital PDFs, linear reading order, images “as-is”) keep the first implementation very achievable.

______________________________________________________________________

If this looks good, I’ll follow up with a **one-page architecture/flow** (CLI flags, file layout, JSON schema we’ll emit for Journal Entries/Pages, and the exact packing commands).

[1]: https://deepwiki.com/foundryvtt/foundryvtt/4.1-journal-entries?utm_source=chatgpt.com "Journal Entries | foundryvtt/foundryvtt | DeepWiki"
[2]: https://foundryvtt.com/api/v12/interfaces/foundry.types.JournalEntryData.html?utm_source=chatgpt.com "JournalEntryData | Foundry Virtual Tabletop - API Documentation ..."
[3]: https://github.com/foundryvtt/foundryvtt-cli?utm_source=chatgpt.com "GitHub - foundryvtt/foundryvtt-cli: The official Foundry VTT CLI"
[4]: https://www.npmjs.com/package/%40foundryvtt/foundryvtt-cli?utm_source=chatgpt.com "@foundryvtt/foundryvtt-cli - npm"
[5]: https://foundryvtt.com/article/journal/?utm_source=chatgpt.com "Journal Entries - Foundry Virtual Tabletop"
[6]: https://foundryvtt.com/api/v12/classes/client.JournalEntry.html?utm_source=chatgpt.com "API Documentation - Version 12 - Foundry Virtual Tabletop"
[7]: https://foundryvtt.com/article/v11-leveldb-packs/?utm_source=chatgpt.com "Version 11 Content Packaging Changes - Foundry Virtual Tabletop"
[8]: https://foundryvtt.com/article/compendium/?utm_source=chatgpt.com "Compendium Packs - Foundry Virtual Tabletop"
[9]: https://github.com/earlSt1/vtt-compendium-folders?utm_source=chatgpt.com "GitHub - earlSt1/vtt-compendium-folders: Collapsible folders in the ..."
[10]: https://foundryvtt.wiki/en/basics/Compendia?utm_source=chatgpt.com "Compendia - Foundry VTT Community Wiki"
[11]: https://foundryvtt.com/api/v12/enums/foundry.CONST.JOURNAL_ENTRY_PAGE_FORMATS.html?utm_source=chatgpt.com "JOURNAL_ENTRY_PAGE_FORMATS | Foundry Virtual Tabletop - API ..."
[12]: https://foundryvtt.com/packages/compendium-folders/?utm_source=chatgpt.com "Compendium Folders - Foundry Virtual Tabletop"
