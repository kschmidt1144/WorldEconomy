import { defineStore } from "pinia";
import { loadInk, saveInk, type InkStroke } from "../lib/ink";
import { useAuthStore } from "./auth";

export type InkMode = "off" | "draw" | "erase";

// pen palette (works on both themes)
export const INK_COLORS = ["#1c2733", "#b42318", "#0d6e78", "#b45309", "#6b4e9e"];

let saveTimer: ReturnType<typeof setTimeout> | null = null;

export const useInkStore = defineStore("ink", {
  state: () => ({
    mode: "off" as InkMode,
    color: "#b42318",
    width: 2.6,
    allowTouch: false, // when true, finger draws too (no-stylus fallback)
    strokes: [] as InkStroke[],
    chapter: "" as string,
    loaded: false,
    saving: false,
  }),
  getters: {
    active: (s) => s.mode !== "off",
    hasInk: (s) => s.strokes.length > 0,
  },
  actions: {
    async loadFor(chapter: string) {
      this.chapter = chapter;
      this.loaded = false;
      if (!useAuthStore().signedIn) {
        this.strokes = [];
        this.loaded = true;
        return;
      }
      this.strokes = await loadInk(chapter);
      this.loaded = true;
    },
    enter() {
      if (this.mode === "off") this.mode = "draw";
    },
    exit() {
      this.mode = "off";
    },
    setMode(m: InkMode) {
      this.mode = m;
    },
    setColor(c: string) {
      this.color = c;
      this.mode = "draw";
    },
    addStroke(s: InkStroke) {
      if (s.p.length >= 2) {
        this.strokes.push(s);
        this.scheduleSave();
      }
    },
    undo() {
      this.strokes.pop();
      this.scheduleSave();
    },
    clear() {
      this.strokes = [];
      this.scheduleSave();
    },
    // remove any stroke passing within `r` (normalized) of (nx, ny)
    eraseAt(nx: number, ny: number, r: number) {
      const before = this.strokes.length;
      this.strokes = this.strokes.filter((st) => {
        for (let i = 0; i < st.p.length; i += 2) {
          const dx = st.p[i] - nx;
          const dy = st.p[i + 1] - ny;
          if (dx * dx + dy * dy <= r * r) return false;
        }
        return true;
      });
      if (this.strokes.length !== before) this.scheduleSave();
    },
    scheduleSave() {
      if (!useAuthStore().signedIn || !this.chapter) return;
      if (saveTimer) clearTimeout(saveTimer);
      saveTimer = setTimeout(async () => {
        this.saving = true;
        try {
          await saveInk(this.chapter, this.strokes);
        } finally {
          this.saving = false;
        }
      }, 900);
    },
  },
});
