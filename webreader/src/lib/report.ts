import MarkdownIt from "markdown-it";
import anchor from "markdown-it-anchor";

export interface ChapterMeta {
  file: string;
  slug: string;
  num: number;
  title: string;
  label: string;
}

export interface Heading {
  id: string;
  text: string;
  level: number;
}

const REPORT_BASE = import.meta.env.BASE_URL + "report";

function slugify(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .slice(0, 64) || "section";
}

const md = new MarkdownIt({ html: false, linkify: true, typographer: true }).use(anchor, {
  slugify,
  level: [1, 2, 3],
  tabIndex: false,
});

export async function loadManifest(): Promise<ChapterMeta[]> {
  const res = await fetch(`${REPORT_BASE}/manifest.json`);
  if (!res.ok) throw new Error("could not load report manifest");
  return (await res.json()) as ChapterMeta[];
}

const cache = new Map<string, string>();

export async function loadChapterHtml(slug: string): Promise<string> {
  if (cache.has(slug)) return cache.get(slug)!;
  const res = await fetch(`${REPORT_BASE}/${slug}.md`);
  if (!res.ok) throw new Error(`could not load chapter ${slug}`);
  const html = md.render(await res.text());
  cache.set(slug, html);
  return html;
}

// After the HTML is in the DOM: point figures at the report asset path, give each
// <figure> a stable id, and lazy-load images. Returns the ordered anchor list.
export function hydrateContent(root: HTMLElement): Heading[] {
  root.querySelectorAll<HTMLImageElement>("img").forEach((img) => {
    const raw = img.getAttribute("src") || "";
    const name = raw.split("/").pop() || "";
    img.src = `${REPORT_BASE}/figures/${name}`;
    // eager: figures have no intrinsic CSS height, so native lazy-loading collapses
    // them to 0px and never triggers. Only the current chapter's figures are in the DOM.
    img.decoding = "async";
    const figId = "fig-" + name.replace(/\.[a-z]+$/i, "");
    if (img.parentElement && img.parentElement.tagName === "P") {
      const fig = document.createElement("figure");
      fig.id = figId;
      fig.dataset.anchorText = (img.getAttribute("alt") || name).trim();
      img.parentElement.replaceWith(fig);
      fig.appendChild(img);
    } else {
      img.id = figId;
    }
  });

  root.querySelectorAll<HTMLTableElement>("table").forEach((t) => {
    if (t.parentElement?.classList.contains("table-wrap")) return;
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    t.replaceWith(wrap);
    wrap.appendChild(t);
  });

  const anchors: Heading[] = [];
  root.querySelectorAll<HTMLElement>("h2[id], h3[id]").forEach((h) => {
    anchors.push({ id: h.id, text: h.textContent || "", level: h.tagName === "H2" ? 2 : 3 });
  });
  return anchors;
}

// Nearest preceding anchor (heading or figure) above a client Y position in `root`.
export function anchorAtY(root: HTMLElement, clientY: number): { id: string; text: string } {
  const candidates = root.querySelectorAll<HTMLElement>("h2[id], h3[id], figure[id]");
  let best: { id: string; text: string } = { id: "", text: "" };
  for (const el of candidates) {
    const top = el.getBoundingClientRect().top;
    if (top <= clientY + 4) {
      best = {
        id: el.id,
        text: el.dataset.anchorText || (el.textContent || "").trim().slice(0, 80),
      };
    } else break;
  }
  return best;
}

export { REPORT_BASE };
