from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path


class PackCompileError(RuntimeError):
    pass


def _resolve_foundry_cli() -> tuple[str, Path | None]:
    """Resolve the Foundry CLI module path and working directory.

    This function tries multiple strategies to find the Foundry CLI:
    1. Local project node_modules (development scenario)
    2. Global npm installation
    3. npx resolution (fallback)

    Returns:
        Tuple of (require_path, working_directory)
        - require_path: Path to use in require() statement
        - working_directory: Directory to run Node.js from (or None for current dir)
    """
    # Strategy 1: Local project node_modules (development scenario)
    current = Path(__file__).parent
    while current != current.parent:  # Stop at filesystem root
        package_json = current / "package.json"
        foundry_cli = current / "node_modules" / "@foundryvtt" / "foundryvtt-cli"

        if package_json.exists() and foundry_cli.exists():
            # Found local installation - use absolute path and project root
            return str(foundry_cli).replace("\\", "/"), current

        current = current.parent

    # Strategy 2: Try to resolve global installation via Node.js
    try:
        result = subprocess.run(
            ["node", "-e", "console.log(require.resolve('@foundryvtt/foundryvtt-cli'))"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        global_path = result.stdout.strip()
        if global_path:
            # Found global installation - use absolute path, no specific working directory
            return global_path.replace("\\", "/"), None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Strategy 3: Fallback to package name (let Node.js resolve it)
    # This works when the CLI is globally installed or available in NODE_PATH
    return "@foundryvtt/foundryvtt-cli", None


def compile_pack(module_dir: Path, pack_name: str) -> None:
    """Compile JSON sources to a LevelDB pack using Foundry CLI via npx.

    - module_dir: path to <out-dir>/<mod-id>
    - pack_name: name of the pack (e.g., <mod-id>-journals)
    """

    sources = module_dir / "sources" / "journals"
    output = module_dir / "packs" / pack_name
    if not sources.exists():
        raise PackCompileError(f"Sources directory not found: {sources}")
    output.mkdir(parents=True, exist_ok=True)

    # Resolve Foundry CLI installation
    try:
        foundry_cli_path, working_directory = _resolve_foundry_cli()
    except Exception as exc:
        raise PackCompileError(
            f"Failed to resolve Foundry CLI installation: {exc}. "
            "Ensure the Foundry CLI is installed via 'npm install -g @foundryvtt/foundryvtt-cli' "
            "or 'npm install @foundryvtt/foundryvtt-cli'."
        ) from exc

    # Build a small Node script on disk to avoid -e quoting issues
    src_js = json.dumps(str(sources).replace("\\", "/"))
    dest_js = json.dumps(str(output).replace("\\", "/"))
    foundry_cli_require = json.dumps(foundry_cli_path)
    node_js = (
        "const fs = require('fs');\n"
        "const path = require('path');\n"
        f"const {{ compilePack }} = require({foundry_cli_require});\n"
        f"const src = {src_js};\n"
        f"const dest = {dest_js};\n"
        "function listJson(dir) {\n"
        "  const out = [];\n"
        "  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {\n"
        "    const p = path.join(dir, entry.name);\n"
        "    if (entry.isDirectory()) out.push(...listJson(p));\n"
        "    else if (entry.isFile() && p.endsWith('.json')) out.push(p);\n"
        "  }\n"
        "  return out;\n"
        "}\n"
        "// Pre-patch: ensure JournalEntry and nested pages have Classic Level _key\n"
        "let patched = 0;\n"
        "let patchedPages = 0;\n"
        "for (const file of listJson(src)) {\n"
        "  try {\n"
        "    const raw = fs.readFileSync(file, 'utf8');\n"
        "    const doc = JSON.parse(raw);\n"
        "    if (doc && typeof doc._id === 'string' && !doc._key) {\n"
        "      doc._key = `!journal!${doc._id}`;\n"
        "      patched++;\n"
        "    }\n"
        "    if (doc && Array.isArray(doc.pages)) {\n"
        "      for (const p of doc.pages) {\n"
        "        if (p && typeof p._id === 'string' && !p._key && typeof doc._id === 'string') {\n"
        "          p._key = `!journal.pages!${doc._id}.${p._id}`;\n"
        "          patchedPages++;\n"
        "        }\n"
        "      }\n"
        "    }\n"
        "    if (patched || patchedPages) {\n"
        "      fs.writeFileSync(file, JSON.stringify(doc, null, 2) + '\\n');\n"
        "    }\n"
        "  } catch (e) { /* ignore */ }\n"
        "}\n"
        "if (patched || patchedPages) {\n"
        "  console.log(`[pdf2foundry] Patched _key on ${patched} root docs`);\n"
        "  console.log(`[pdf2foundry] Patched _key on ${patchedPages} pages`);\n"
        "}\n"
        "const transformEntry = async (doc) => doc;\n"
        "compilePack(src, dest, { log: true, recursive: true, transformEntry })\n"
        ".then(()=>process.exit(0))\n"
        ".catch(e=>{\n"
        "  console.error(e?.stack||e?.message||e);\n"
        "  process.exit(1);\n"
        "});\n"
    )

    script_path = output.parent / "__compile_pack.js"
    script_path.write_text(node_js, encoding="utf-8")
    cmd = ["node", str(script_path)]
    try:
        # Run Node.js from the resolved working directory (if any)
        subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=working_directory)
    except subprocess.CalledProcessError as exc:
        raise PackCompileError(f"Foundry CLI failed (exit {exc.returncode}): {exc.stderr or exc.stdout}") from exc
    finally:
        with contextlib.suppress(Exception):
            script_path.unlink()
