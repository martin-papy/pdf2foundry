# CLI → GUI Control Map (PySide6)

## A) Required (Main window)

| CLI           | GUI Control            | Default | Validation                    | Notes / Tooltip                      | UI Placement          |
| ------------- | ---------------------- | ------- | ----------------------------- | ------------------------------------ | --------------------- |
| `<PDF_FILE>`  | FilePicker + Drag&Drop | —       | must exist, `.pdf`            | “Select a source PDF.”               | Main → Drop zone      |
| `--mod-id`    | LineEdit               | (none)  | lowercase, hyphens, no spaces | “Unique module ID (e.g. `my-book`).” | Main → “Module” group |
| `--mod-title` | LineEdit               | (none)  | non-empty                     | “Display name shown in Foundry.”     | Main → “Module” group |

## B) Module options

| CLI                                            | GUI Control | Default             | Validation | Notes / Tooltip                         | UI Placement          |
| ---------------------------------------------- | ----------- | ------------------- | ---------- | --------------------------------------- | --------------------- |
| `--author`                                     | LineEdit    | “”                  | free text  | “Author metadata for module.json.”      | Settings → General    |
| `--license`                                    | LineEdit    | “”                  | free text  | “License string for module.json.”       | Settings → General    |
| `--pack-name`                                  | LineEdit    | `<mod-id>-journals` | non-empty  | “Compendium pack name.”                 | Settings → General    |
| `--toc / --no-toc`                             | CheckBox    | ON                  | —          | “Create a Table of Contents entry.”     | Settings → Conversion |
| `--deterministic-ids / --no-deterministic-ids` | CheckBox    | ON                  | —          | “Stable IDs for repeatable cross-refs.” | Settings → General    |

## C) Content processing

| CLI                         | GUI Control                           | Default      | Validation               | Notes / Tooltip                                          | UI Placement              |                                                                |                       |
| --------------------------- | ------------------------------------- | ------------ | ------------------------ | -------------------------------------------------------- | ------------------------- | -------------------------------------------------------------- | --------------------- |
| \`--tables auto             | structured                            | image-only\` | ComboBox                 | `auto`                                                   | enum                      | “How to handle tables.”                                        | Settings → Conversion |
| \`--ocr auto                | on                                    | off\`        | ComboBox                 | `auto`                                                   | enum                      | “OCR pages when needed / always / never.” (Tesseract required) | Settings → Conversion |
| \`--picture-descriptions on | off\`                                 | CheckBox     | OFF                      | —                                                        | “AI captions for images.” | Settings → Conversion                                          |                       |
| `--vlm-repo-id <model>`     | LineEdit (disabled until above is ON) | empty        | non-empty if captions ON | “Hugging Face model (e.g. `microsoft/Florence-2-base`).” | Settings → Conversion     |                                                                |                       |

## D) Performance

| CLI                | GUI Control                   | Default   | Validation                           | Notes / Tooltip                          | UI Placement           |
| ------------------ | ----------------------------- | --------- | ------------------------------------ | ---------------------------------------- | ---------------------- |
| `--pages "<spec>"` | LineEdit + Helper (“Preview”) | all pages | regex `^(\d+(-\d+)?)(,\d+(-\d+)?)*$` | “Page list/ranges, e.g. `1,5-10,15`.”    | Settings → Performance |
| `--workers <n>`    | SpinBox (1..N cores)          | 1         | integer ≥1                           | “Worker processes for CPU tasks.”        | Settings → Performance |
| `--reflow-columns` | CheckBox                      | OFF       | —                                    | “Experimental multi-column text reflow.” | Settings → Performance |

## E) Caching (single-pass ingestion)

| CLI                                                          | GUI Control            | Default | Validation    | Notes / Tooltip                               | UI Placement       |
| ------------------------------------------------------------ | ---------------------- | ------- | ------------- | --------------------------------------------- | ------------------ |
| `--docling-json <path>`                                      | FilePicker (Save/Open) | empty   | writable path | “Cache file to load/save Docling JSON.”       | Settings → Caching |
| `--write-docling-json / --no-write-docling-json`             | CheckBox               | OFF     | —             | “Auto-save to default cache location.”        | Settings → Caching |
| `--fallback-on-json-failure / --no-fallback-on-json-failure` | CheckBox               | ON      | —             | “If cache load fails, do a fresh conversion.” | Settings → Caching |

## F) Output

| CLI                                  | GUI Control                                    | Default | Validation        | Notes / Tooltip                         | UI Placement      |
| ------------------------------------ | ---------------------------------------------- | ------- | ----------------- | --------------------------------------- | ----------------- |
| `--out-dir <path>`                   | FolderPicker                                   | `dist`  | writable dir      | “Where the module will be written.”     | Main → Output     |
| `--compile-pack / --no-compile-pack` | CheckBox                                       | OFF     | —                 | “Compile LevelDB pack via Foundry CLI.” | Settings → Output |
| `--verbose` / `-v` (repeatable)      | ComboBox: Verbosity (Normal / Verbose / Debug) | Normal  | map to `-v` count | “Increase logging detail.”              | Settings → Debug  |

______________________________________________________________________

## Dependencies & enable/disable rules

- **Image captions**: when “Picture descriptions” is ON, **require** a non-empty `vlm-repo-id`. Show a warning if empty on Convert.
- **OCR**: Show an inline tip if Tesseract isn’t detected (optional check) before starting.
- **Compile pack**: Show helper text about Node LTS + Foundry CLI; if not found, disable with tooltip.
- **Pages**: provide a “Validate” helper that turns the field red + tooltip when the pattern doesn’t match.

______________________________________________________________________

## Main window (command synthesis)

On **Convert**, synthesize the CLI equivalent using the above controls in this order:

1. `convert <PDF_FILE> --mod-id <id> --mod-title <title>`
1. Module options (author, license, pack name, toc, deterministic-ids)
1. Content (tables, ocr, picture-descriptions + vlm-repo-id)
1. Performance (pages, workers, reflow-columns)
1. Caching (docling-json, write-docling-json, fallback-on-json-failure)
1. Output (out-dir, compile-pack)
1. Verbosity flags (`-v`, `-vv`)

Show the full synthesized command in a read-only text box inside the **Logs** pane (copy-button) for transparency.

______________________________________________________________________

## Validation details (quick spec)

- `mod-id`: regex `^[a-z0-9]+(?:-[a-z0-9]+)*$` (error if empty/invalid).
- `mod-title`: required, non-empty.
- `pack-name`: required, non-empty (defaults when blank on blur to `<mod-id>-journals`).
- `workers`: 1..logical CPU cores (detect via `os.cpu_count()`; cap at 32).
- `pages`: allow empty (all pages) or the pattern noted above, with inline errors.
- `out-dir` must be creatable (test on blur; if not, show warning with “Create?”).

______________________________________________________________________

## Tooltips (one-liners your devs can paste)

- Tables: “auto/structured/image-only for table handling.”
- OCR: “auto (low text pages), on (all pages), off (never). Requires Tesseract.”
- Picture descriptions: “Generate AI captions using a VLM (downloaded on first run).”
- VLM repo: “Hugging Face model ID, e.g. `Salesforce/blip-image-captioning-base`.”
- Deterministic IDs: “Stable SHA1-based IDs to keep links consistent.”
- Compile pack: “Build a LevelDB compendium (Foundry CLI + Node required).”

______________________________________________________________________

## Presets (local JSON)

- Path: `~/.pdf2foundry/presets/*.json`
- Stores: every control above (including last used `out-dir`).
- Buttons: **Load / Save / Delete**; “Save as…” prompts preset name; confirm overwrite.

______________________________________________________________________

## Logging & update UX (non-CLI but in PRD)

- **Export Logs**: writes current session log to a user-selected file.
- **Update Check**: on app start, hit GitHub Releases; if newer, show non-blocking banner with “Download” (opens browser).
- **Report Issue**: Help menu → opens GitHub Issues.
