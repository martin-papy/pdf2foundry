/* eslint-disable no-console */
// Debug compiler for Foundry packs with verbose diagnostics
// Usage: node scripts/compile-pack-debug.js --module <dist/mod-id> --pack <pack-name>

const fs = require('fs');
const path = require('path');

async function main() {
  const args = process.argv.slice(2);
  const arg = (name, def) => {
    const idx = args.indexOf(`--${name}`);
    return idx >= 0 ? args[idx + 1] : def;
  };

  const moduleDir = path.resolve(arg('module', 'dist/adc-v7'));
  const packName = arg('pack', 'adc-v7-journals');
  const srcDir = path.join(moduleDir, 'sources', 'journals');
  const destDir = path.join(moduleDir, 'packs', packName);

  console.log('Node version:', process.version);
  console.log('Module dir:', moduleDir);
  console.log('Source dir :', srcDir);
  console.log('Dest dir   :', destDir);

  if (!fs.existsSync(srcDir)) {
    console.error('ERROR: sources directory not found:', srcDir);
    process.exit(2);
  }

  // Pre-scan all JSON docs
  const listJsonFiles = (dir) => {
    const out = [];
    const walk = (d) => {
      for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
        const p = path.join(d, entry.name);
        if (entry.isDirectory()) walk(p);
        else if (entry.isFile() && p.endsWith('.json')) out.push(p);
      }
    };
    walk(dir);
    return out;
  };

  const files = listJsonFiles(srcDir).sort();
  console.log(`Found ${files.length} source JSON files`);
  let valid = 0;
  let patchedKeys = 0;
  let patchedPageKeys = 0;
  for (const file of files) {
    try {
      const raw = fs.readFileSync(file, 'utf-8');
      const doc = JSON.parse(raw);
      const pid = typeof doc._id === 'string' ? doc._id : '<missing>';
      const name = typeof doc.name === 'string' ? doc.name : '<missing>';
      const pages = Array.isArray(doc.pages) ? doc.pages.length : 0;
      console.log(` - ${path.basename(file)}: _id=${pid} name="${name}" pages=${pages}`);
      if (pid !== '<missing>' && name !== '<missing>' && pages >= 0) valid += 1;
      if (pid !== '<missing>' && !doc._key) {
        doc._key = `!journal!${pid}`;
        patchedKeys += 1;
      }
      if (Array.isArray(doc.pages)) {
        for (const p of doc.pages) {
          if (p && typeof p._id === 'string' && !p._key && pid !== '<missing>') {
            p._key = `!journal.pages!${pid}.${p._id}`;
            patchedPageKeys += 1;
          }
        }
      }
      if (patchedKeys || patchedPageKeys) fs.writeFileSync(file, JSON.stringify(doc, null, 2) + '\n');
    } catch (e) {
      console.error('   ! Failed to parse', file, e?.message || e);
    }
  }
  console.log(`Valid documents: ${valid}/${files.length}`);
  if (patchedKeys || patchedPageKeys) console.log(`Patched _key on ${patchedKeys} root docs and ${patchedPageKeys} pages`);

  // Ensure destination exists
  fs.mkdirSync(destDir, { recursive: true });

  // Compile with transform that guarantees _key and returns doc
  console.log('\nStarting compilePack with verbose logging...');
  const { compilePack } = require('@foundryvtt/foundryvtt-cli');

  const transformEntry = async (doc) => {
    try {
      if (doc && typeof doc._id === 'string' && !doc._key) {
        doc._key = `!journal!${doc._id}`;
      }
    } catch (e) {
      console.error('transformEntry error for _id', doc?._id, e?.message || e);
    }
    return doc;
  };

  try {
    await compilePack(srcDir, destDir, { log: true, recursive: true, transformEntry });
    console.log('compilePack finished successfully.');
  } catch (e) {
    console.error('compilePack failed:', e?.stack || e?.message || e);
    process.exit(1);
  }
}

main();


