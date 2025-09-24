# Wireframes

## 1. Main Window (Basic Mode)

```ascii
 --------------------------------------------------------
| pdf2foundry GUI                               [?] ⚙️  |
|--------------------------------------------------------|
|                                                        |
|   [📂 Drag & Drop your PDF here]                       |
|                                                        |
|    OR                                                  |
|                                                        |
|   [ Browse Files... ]                                  |
|                                                        |
|--------------------------------------------------------|
| Output Folder: [ /user/output/path              ] [📁] |
|--------------------------------------------------------|
|                                                        |
|                [   Convert   ]                         |
|                                                        |
|--------------------------------------------------------|
| Progress: [███████-------]  45%                        |
|                                                        |
| ▼ Logs (collapsible)                                   |
| -----------------------------------------------------  |
| > Converting file...                                   |
| > Extracting TOC...                                    |
| > Success: Compendium saved to /user/output/path       |
| -----------------------------------------------------  |
| [ Open Output Folder ]   [ Export Logs ]               |
 --------------------------------------------------------
```

**Notes:**

- Top-right: `?` = Help (links to GitHub/Docs), ⚙️ = Settings (Advanced mode).
- Center: Drag & Drop zone + Browse button.
- Bottom: Progress + collapsible logs.
- Utility: Export Logs + Open Folder.

______________________________________________________________________

## 2. Settings Window (Advanced Mode)

```ascii
 --------------------------------------------------------
| Settings                                     [ Save ]  |
|--------------------------------------------------------|
| [General] [Conversion] [Debug] [Presets]               |
|--------------------------------------------------------|

 General Tab:
 --------------------------------------------------------
| Compendium Name: [ Default ]                           |
| Overwrite Existing: [x]                                |
| Deterministic IDs: [x]                                 |
 --------------------------------------------------------

 Conversion Tab:
 --------------------------------------------------------
| Split PDF into Pages: [ ]                              |
| Generate TOC: [x]                                      |
| Preserve Internal Links: [x]                           |
| Handle Tables: [Dropdown: Images / Parse / Skip]       |
 --------------------------------------------------------

 Debug Tab:
 --------------------------------------------------------
| Verbose Logging: [x]                                   |
| Save Temporary Files: [ ]                              |
| [ Export Logs ]                                        |
 --------------------------------------------------------

 Presets Tab:
 --------------------------------------------------------
| Saved Presets:                                         |
|  - DnD_5e_Config.json                                  |
|  - CoC_Ruleset.json                                    |
|                                                        |
| [ Load ] [ Save Current ] [ Delete ]                   |
 --------------------------------------------------------

 [ Cancel ]                                [ Apply ]
 --------------------------------------------------------
```

**Notes:**

- Tabs organize advanced options clearly.
- Tooltips for each checkbox/dropdown to explain CLI mapping.
- Presets saved locally (JSON in `~/.pdf2foundry/presets/`).

______________________________________________________________________

## 3. About / Help Window

```ascii
 --------------------------------------------------------
| About pdf2foundry GUI                                  |
|--------------------------------------------------------|
| Version: v1.0.0                                        |
| GitHub: [ Open Repository ]                            |
| Report Issue: [ Open GitHub Issues ]                   |
|                                                        |
| © 2025 Your Name                                       |
 --------------------------------------------------------
```

______________________________________________________________________

✅ These wireframes cover:

- **Main flow** (drop file → convert → view logs).
- **Advanced options** (all flags in organized tabs).
- **Utility features** (update checks, logs export, issue reporting).
