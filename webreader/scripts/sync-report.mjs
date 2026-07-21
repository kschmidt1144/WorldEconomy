// Copies the compiled report's chapter markdown + figures into public/report/
// and writes a manifest the app reads. Run automatically before dev/build.
import { readdir, readFile, mkdir, copyFile, writeFile, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoReport = resolve(here, "..", "..", "report");
const outDir = resolve(here, "..", "public", "report");
const figSrc = join(repoReport, "figures");
const figOut = join(outDir, "figures");

function titleFrom(md) {
  const h1 = md.split("\n").find((l) => l.startsWith("# "));
  if (!h1) return null;
  return h1.replace(/^#\s+/, "").trim();
}

// "Chapter 10 — The Chokepoints: ..." -> { label: "The Chokepoints", part: "Chapter 10" }
function shortLabel(title) {
  const m = title.match(/^(Chapter\s+\d+|[A-Za-z].*?)\s*[—-]\s*(.+)$/);
  if (!m) return title;
  const rest = m[2].split(":")[0].trim();
  return rest || title;
}

async function main() {
  if (!existsSync(repoReport)) {
    console.error(`[sync] report dir not found at ${repoReport}`);
    process.exit(1);
  }
  await rm(outDir, { recursive: true, force: true });
  await mkdir(figOut, { recursive: true });

  const files = (await readdir(repoReport))
    .filter((f) => /^\d\d-.*\.md$/.test(f))
    .sort();

  const manifest = [];
  for (const file of files) {
    const md = await readFile(join(repoReport, file), "utf8");
    await copyFile(join(repoReport, file), join(outDir, file));
    const num = parseInt(file.slice(0, 2), 10);
    const title = titleFrom(md) || file;
    manifest.push({ file, slug: file.replace(/\.md$/, ""), num, title, label: shortLabel(title) });
  }

  // copy figures referenced anywhere (just copy the whole dir — it's the report's asset set)
  let nFig = 0;
  if (existsSync(figSrc)) {
    for (const f of await readdir(figSrc)) {
      if (f.endsWith(".png")) {
        await copyFile(join(figSrc, f), join(figOut, f));
        nFig++;
      }
    }
  }

  await writeFile(join(outDir, "manifest.json"), JSON.stringify(manifest, null, 2));
  console.log(`[sync] ${manifest.length} chapters + ${nFig} figures -> public/report/`);
}

main();
