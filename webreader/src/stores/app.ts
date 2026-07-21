import { defineStore } from "pinia";
import { loadManifest, type ChapterMeta, type Heading } from "../lib/report";
import { storage, type Progress } from "../lib/storage";

type Theme = "light" | "dark";
const THEME_KEY = "we-reader:theme";

function initialTheme(): Theme {
  const saved = localStorage.getItem(THEME_KEY) as Theme | null;
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export const useAppStore = defineStore("app", {
  state: () => ({
    chapters: [] as ChapterMeta[],
    currentSlug: "" as string,
    theme: initialTheme() as Theme,
    sidebarOpen: false,
    notesOpen: false,
    resume: null as Progress | null,
    loaded: false,
    headings: [] as Heading[],
    activeHeading: "" as string,
    pendingAnchor: "" as string,
  }),
  getters: {
    current(state): ChapterMeta | undefined {
      return state.chapters.find((c) => c.slug === state.currentSlug);
    },
    currentIndex(state): number {
      return state.chapters.findIndex((c) => c.slug === state.currentSlug);
    },
  },
  actions: {
    applyTheme() {
      document.documentElement.dataset.theme = this.theme;
    },
    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, this.theme);
      this.applyTheme();
    },
    async init() {
      this.applyTheme();
      this.chapters = await loadManifest();
      this.resume = await storage.getProgress();
      this.currentSlug = this.resume?.chapter || this.chapters[0]?.slug || "";
      this.loaded = true;
    },
    goto(slug: string) {
      if (this.chapters.some((c) => c.slug === slug)) {
        this.currentSlug = slug;
        this.sidebarOpen = false;
      }
    },
    nav(delta: number) {
      const i = this.currentIndex + delta;
      if (i >= 0 && i < this.chapters.length) this.goto(this.chapters[i].slug);
    },
    jumpTo(chapter: string, anchor: string) {
      this.pendingAnchor = anchor;
      this.goto(chapter);
      this.notesOpen = false;
    },
    saveProgress(ratio: number) {
      const p: Progress = { chapter: this.currentSlug, ratio, updatedAt: Date.now() };
      this.resume = p;
      void storage.setProgress(p);
    },
  },
});
