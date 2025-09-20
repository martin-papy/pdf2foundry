# Templates

1. a **sample `module.json`** (v13 manifest with a Journal compendium, CSS, and native pack folders), and
1. a **sample Journal Entry source JSON** (one “Chapter” with two HTML pages, deterministic IDs, images, and an example `@UUID[...]` link).

I’ve also added short notes (right after each block) that call out the few fields you’ll want to parameterize in the CLI.

______________________________________________________________________

## 1) Sample `module.json` (v13)

```json
{
  "id": "pdf2foundry-my-book",
  "title": "My Book (PDF Import)",
  "description": "Imported Journals generated from a PDF using PDF2Foundry.",
  "version": "1.0.0",
  "authors": [
    { "name": "APAC Corp Services", "email": "martin.papy@cbtw.tech" }
  ],
  "compatibility": {
    "minimum": "12",
    "verified": "12"
  },
  "relationships": {
    "requires": [
      { "id": "compendium-folders", "type": "module", "compatibility": { "minimum": "12" } }
    ]
  },
  "packs": [
    {
      "name": "my-book-journals",
      "label": "My Book — Journals",
      "path": "packs/my-book-journals",
      "type": "JournalEntry"
    }
  ],
  "styles": [
    "styles/pdf2foundry.css"
  ],
  "media": [
    {
      "type": "cover",
      "url": "assets/cover.png"
    }
  ],
  "url": "https://example.com/pdf2foundry",
  "manifest": "https://example.com/pdf2foundry/module.json",
  "download": "https://example.com/pdf2foundry/module.zip",
  "readme": "https://example.com/pdf2foundry/README.md",
  "license": "OGL-1.0a"
}
```

### Notes for devs (module.json)

- `compatibility` and `authors` follow the modern manifest rules (v10+). ([Foundry Virtual Tabletop][1])
- `packs[].path` is a **folder** (LevelDB), not a `*.db` file (v11+ content format). ([Foundry Virtual Tabletop][2])
- The “Module Manifest” rules (folder name must equal `id`, etc.) are described here. ([Foundry Virtual Tabletop][3])
- The “Packaging Guide” explains the recommended content-packaging flow (and the Module Maker UI, if you build in-app). ([Foundry Virtual Tabletop][4])

______________________________________________________________________

## 2) Sample **Journal Entry** source file (for `sources/journals/ch01.json`)

> This shows **one Journal Entry** (“Chapter 1 — Introduction”) with **two HTML pages**.
>
> - Uses **deterministic IDs** (`_id`) you’ll compute in the CLI.
> - Uses **HTML** page format (v13 supports HTML and Markdown).
> - Demonstrates a **Compendium Folders** inner-pack folder path via flags.
> - Shows how an **image** in `/assets/` is referenced from HTML.
> - Shows an example **`@UUID[...]` link** pointing to another page (replace IDs at build-time). (Docs on ids/uuids here.) ([Foundry VTT Wiki][6])

```json
{
  "_id": "a1b2c3d4e5f6a7b8",
  "name": "Chapter 1 — Introduction",
  "folder": null,
  "flags": {
    "compendium-folders": {
      "folderPath": ["My Book", "Chapter 1"]
    }
  },
  "ownership": { "default": 0 },
  "pages": [
    {
      "_id": "p111222333444555",
      "name": "Overview",
      "type": "text",
      "title": { "show": true, "level": 1 },
      "text": {
        /* IMPORTANT: many packers accept numeric CONST values. If strings aren't accepted by your packer, set format to 1. */
        "format": 1,
        "content": "<div class='pdf2foundry'><h2>Overview</h2><p>This chapter introduces the setting and goals.</p><figure><img src='modules/pdf2foundry-my-book/assets/fig-001.png' alt='Intro Figure'><figcaption>Figure 1: Setting overview</figcaption></figure><p>Jump to <a href='@UUID[JournalEntry.a1b2c3d4e5f6a7b8.JournalEntryPage.p666777888999000]{Key Concepts}</a>.</p></div>"
      },
      "sort": 1000
    },
    {
      "_id": "p666777888999000",
      "name": "Key Concepts",
      "type": "text",
      "title": { "show": true, "level": 2 },
      "text": {
        "format": 1,
        "content": "<div class='pdf2foundry'><h3>Key Concepts</h3><ul><li>Concept A</li><li>Concept B</li></ul><p>Return to <a href='@UUID[JournalEntry.a1b2c3d4e5f6a7b8.JournalEntryPage.p111222333444555]{Overview}</a>.</p></div>"
      },
      "sort": 2000
    }
  ]
}
```

### Notes for devs (journal entry)

- **Page format:** v13 exposes `JOURNAL_ENTRY_PAGE_FORMATS` (HTML/Markdown). Many exporters/packers represent **HTML as `1`**. If your pack compiler rejects string enums, set `"format": 1`.
- **HTML content:** The article confirms journal pages can be **edited as raw HTML**; keeping our markup semantic and simple avoids editor surprises. ([Foundry Virtual Tabletop][7])
- **IDs & UUIDs:** Foundry distinguishes `id` vs `uuid`. At runtime, the UUID will incorporate the compendium and document ID, enabling `@UUID[...]` links. We pre-generate stable `_id`s so cross-refs remain valid across rebuilds. ([Foundry VTT Wiki][6])
- **Inner folders:** Core supports folders for compendia in the sidebar, but **folders inside a pack** rely on the Compendium Folders module; we store the folder path under its flag so the add-on can rebuild hierarchy. ([Foundry Virtual Tabletop][8])

______________________________________________________________________

## How to turn `sources/journals/*.json` into a **LevelDB pack**

You have three practical options:

- **Use Foundry’s built-in Module Maker UI (recommended by the docs)** to author/import and build your pack interactively (great for verifying fields). ([Foundry Virtual Tabletop][4])
- **Use a packer that writes LevelDB packs** from JSON (for headless/CLI builds).
- Or build JSON → LevelDB with your own script—as long as the output matches the **v11+ LevelDB** pack layout (i.e., a **folder** at `packs/<name>/` rather than a `.db` file). ([Foundry Virtual Tabletop][2])

> Regardless of the route, ensure your final module’s `packs[].path` points at the **folder** you produced (e.g., `packs/my-book-journals/`).

______________________________________________________________________

## Tiny CSS scaffold (optional, safe & additive)

```css
/* styles/pdf2foundry.css */
.pdf2foundry h1, .pdf2foundry h2, .pdf2foundry h3 { margin-top: 0.6em; }
.pdf2foundry figure { margin: 1em 0; text-align: center; }
.pdf2foundry figcaption { font-size: 0.9em; opacity: 0.8; }
.pdf2foundry img { max-width: 100%; height: auto; }
```

This keeps layout tidy without fighting Foundry’s journal styles.

______________________________________________________________________

If you want, I can also generate a **TOC entry template** (with `@UUID` placeholders) and a **deterministic ID helper** (Python snippet) you can paste straight into the CLI.

<!-- v13 API deep links can be added when stabilized -->

[1]: https://foundryvtt.com/article/migration/?utm_source=chatgpt.com "API Migration Guides | Foundry Virtual Tabletop"
[2]: https://foundryvtt.com/article/v11-leveldb-packs/?utm_source=chatgpt.com "Version 11 Content Packaging Changes - Foundry Virtual Tabletop"
[3]: https://foundryvtt.com/article/module-development/?utm_source=chatgpt.com "Introduction to Module Development - Foundry Virtual Tabletop"
[4]: https://foundryvtt.com/article/packaging-guide/?utm_source=chatgpt.com "Content Packaging Guide - Foundry Virtual Tabletop"
[6]: https://foundryvtt.wiki/en/development/api/document?utm_source=chatgpt.com "Document | Foundry VTT Community Wiki"
[7]: https://foundryvtt.com/article/journal/?utm_source=chatgpt.com "Journal Entries - Foundry Virtual Tabletop"
[8]: https://foundryvtt.com/article/compendium/?utm_source=chatgpt.com "Compendium Packs - Foundry Virtual Tabletop"
