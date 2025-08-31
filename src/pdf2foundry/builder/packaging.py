from __future__ import annotations

import subprocess
from pathlib import Path


class PackCompileError(RuntimeError):
    pass


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

    # Prefer using the API via node -e to avoid global config requirements
    node_js = (
        "const { compilePack } = require('@foundryvtt/foundryvtt-cli');\n"
        f"const src = '{str(sources).replace('\\\\', '/')}';\n"
        f"const dest = '{str(output).replace('\\\\', '/')}';\n"
        "const transformEntry = async (doc) => {\n"
        "  // Ensure a Classic Level _key for JournalEntry documents\n"
        "  const ok = doc && typeof doc._id === 'string';\n"
        "  if (!doc._key && ok) { doc._key = `!journal!${doc._id}`; }\n"
        "  return doc;\n"
        "};\n"
        "compilePack(src, dest, { log: true, recursive: true, transformEntry })\n"
        ".then(()=>process.exit(0)).catch(e=>{console.error(e?.stack||e?.message||e);process.exit(1);});"
    )
    cmd = ["node", "-e", node_js]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise PackCompileError(
            f"Foundry CLI failed (exit {exc.returncode}): {exc.stderr or exc.stdout}"
        ) from exc
