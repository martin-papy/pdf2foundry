# Product Requirements Document (PRD) for GUI implementation

**Project:** pdf2foundry GUI
**Date:** September 2025
**Owner:** Martin Papy
**Version:** 1.1

______________________________________________________________________

## 1. Overview

The current `pdf2foundry` project is a Python-based CLI tool that converts rich PDF documents (e.g., RPG rulebooks) into structured Foundry VTT compendium packs. While powerful, the CLI interface is intimidating to non-technical users.

The goal of this project is to build a **cross-platform GUI using PySide6** that makes the tool accessible, intuitive, and visually appealing while preserving advanced functionality for power users.

The GUI should:

- Offer a clean, wizard-like workflow for casual users.
- Provide advanced configuration panels for expert users with **full CLI flag parity**.
- Maintain cross-platform support (Windows, macOS, Linux) from day one.
- Include convenience features (logs export, self-update, issue reporting).

______________________________________________________________________

## 2. Target Users

1. **Casual GMs / Players**

   - Limited technical knowledge.
   - Want to quickly convert PDFs without learning CLI options.

1. **Advanced Power Users**

   - Familiar with CLI or scripting.
   - Need fine-grained control over conversion (output format, compendium structure, deterministic IDs, etc.).

______________________________________________________________________

## 3. Goals & Non-Goals

### Goals

- Provide a **desktop GUI** for pdf2foundry (Windows, macOS, Linux).
- Create a **guided flow** (step-by-step wizard) for basic users.
- Allow **direct access to advanced options** via expandable panels or settings tabs.
- Support **drag-and-drop PDF upload**.
- Show **conversion progress and logs** in real-time.
- Provide clear **success/failure notifications** and clickable links to output.
- Provide **self-update check** on startup.
- Allow users to **export logs** for troubleshooting.
- Provide a **Report Issue** shortcut to GitHub.

### Non-Goals

- Replacing CLI functionality (CLI remains for scripting).
- Implementing new conversion logic (core functionality stays in backend).
- Building a web-based version (desktop only).
- Custom accessibility work (basic Qt support only).

______________________________________________________________________

## 4. User Stories

### Core

- As a user, I want to drag & drop a PDF so I don’t have to browse manually.
- As a user, I want a simple **“Convert”** button so I can quickly start processing.
- As a user, I want to see a **progress bar and logs** so I know what’s happening.
- As a user, I want to open the output folder directly from the UI.

### Advanced

- As a power user, I want to configure **all CLI options** in a **Settings panel**.
- As a power user, I want to **save and load presets** for my common configurations.
- As a power user, I want to toggle between **basic mode** and **advanced mode**.

### Utility

- As a user, I want the app to **notify me if a new version is available**.
- As a user, I want to **export logs to a file** for troubleshooting.
- As a user, I want to **quickly report an issue** via GitHub.

______________________________________________________________________

## 5. Functional Requirements

### 5.1 Core Features

- File input (Drag & drop + File browser).
- Output directory selection.
- Start / Stop conversion.
- Real-time log console.
- Progress bar + status indicator.
- Open output folder button.

### 5.2 Advanced Features

- Settings tab with **all CLI options exposed**.
- Tooltips/descriptions for each advanced option.
- Profiles / Presets (saved locally as JSON).
- Advanced logging (debug mode).

### 5.3 Utility Features

- **Self-update checker**: compare current version with GitHub Releases API.
- **Log export**: save logs to file.
- **Report Issue button**: link to GitHub Issues.

### 5.4 Error Handling

- Graceful error popups with meaningful messages.
- Warnings for invalid files or missing dependencies.

______________________________________________________________________

## 6. UI/UX Requirements

### Design Principles

- **Minimalist default view** → users see only the essentials first.
- **Progressive disclosure** → advanced options hidden until expanded.
- **Modern desktop style** → flat, clean, consistent with OS.
- **Light branding** → app logo/icon, otherwise native look.

### Layout

#### Main Window (Basic Mode)

- **Top Bar**: App name + About + Settings + Help (Report Issue).

- **Central Area**:

  - Drag & Drop zone (with icon + text).
  - File browser button.
  - Output folder selector.

- **Bottom Area**:

  - Convert button (primary, large).
  - Progress bar + log console (collapsible).

#### Settings Window (Advanced Mode)

- Tabs or collapsible panels:

  - General (output name, overwrite, deterministic IDs).
  - Conversion (split pages, TOC, internal links).
  - Debug (verbose logging, export logs).

- Save / Load Presets.

______________________________________________________________________

## 7. Technical Requirements

- **Framework**: PySide6 (Qt for Python).

- **Packaging**: PyInstaller or Briefcase to generate `.exe` / `.app` / Linux AppImage.

- **Architecture**:

  - GUI layer calls CLI logic via internal Python functions (not subprocess).
  - Backend (existing pdf2foundry logic) remains untouched.
  - Signals/slots for progress + logs.

- **Presets**: stored locally as JSON under user directory.

- **Update check**: call GitHub Releases API on startup, compare semantic versions.

______________________________________________________________________

## 8. Success Metrics

- Reduced setup friction: 80% of non-technical users can complete a conversion without documentation.
- Parity: All CLI options accessible in advanced mode.
- Stability: No crashes during large file processing (>200 pages).
- Utility adoption: At least 50% of users use logs export or auto-update feature within first release cycle.

______________________________________________________________________

## 9. Risks & Mitigations

- **Risk:** Feature creep in advanced settings may overwhelm UI.

  - *Mitigation:* Use collapsible sections and presets.

- **Risk:** Packaging cross-platform apps may be complex.

  - *Mitigation:* Start with automated GitHub Actions builds for each OS.

- **Risk:** Long conversions may freeze UI.

  - *Mitigation:* Run backend in worker threads, never block UI thread.

- **Risk:** GitHub API rate limits could block update checks.

  - *Mitigation:* Cache last check and limit to once per session.

______________________________________________________________________

## 10. Next Steps

1. Build wireframes (low-fidelity sketches).
1. Define mapping of **all CLI flags → GUI controls**.
1. Implement minimal MVP (drag-drop PDF + Convert + Progress).
1. Expand to advanced settings and presets.
1. Add utility features (update check, logs export, report issue).
1. Package and test on all platforms.
