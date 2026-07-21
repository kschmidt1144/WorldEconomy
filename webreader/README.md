# webreader — World Economy Lab report reader (Kykli PWA)

Read the compiled report and take **margin notes** on a tablet, offline. Notes anchor to
the chapter + nearest heading/figure. This is **M1**: the full reader + note-taking, with
notes on `localStorage`. M2 swaps the storage adapter for Firestore (named DB
`worldeconomy`); M3 exposes those notes to the `econlab` MCP; M4 bakes the build into Kykli.

## Run

```bash
cd webreader
npm install --cache "$PWD/.npmcache"   # repo-local cache (avoids the machine's EACCES)
npm run dev                            # sync report -> public/, start Vite
```

`npm run sync` (auto-run before dev/build) copies `../report/*.md` + `../report/figures/`
into `public/report/` and writes `manifest.json`. Re-run after `econ compile` regenerates
the report.

## Shape

- `src/lib/report.ts` — manifest load, markdown→HTML (markdown-it + anchors), figure path
  rewrite, table wrapping, "nearest anchor" resolver for selections.
- `src/lib/storage.ts` — `StorageAdapter` interface + `LocalStorageAdapter` (M1). **Swap
  the exported `storage` for a `FirestoreAdapter` in M2 — nothing else changes.**
- `src/stores/{app,notes}.ts` — Pinia. Chapters, theme, resume position; notes CRUD.
- `src/components/` — `Reader` (render + scroll-spy + selection), `Sidebar` (TOC),
  `NotesDrawer` (editor + list), `SelectionPopover`, `AppHeader`.

## Notes data model (shared with M2/M3)

`{ id, chapter, chapterTitle, anchor, anchorText, quote, body, color, createdAt, updatedAt }`
→ Firestore collection `notes` in DB `worldeconomy`; the `econlab` MCP will expose
`econ_notes` / `econ_note_add` over the same store.

## Deploy (M4)

`npm run build` → `dist/` (base `/worldeconomy/`) → copy into `Kykli/worldeconomy-dist/`,
nginx serves it at `kykli.dev/worldeconomy`.
