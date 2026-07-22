import { defineStore } from "pinia";
import { storage, newId, type Note } from "../lib/storage";
import { useAuthStore } from "./auth";

export interface DraftNote {
  chapter: string;
  chapterTitle: string;
  anchor: string;
  anchorText: string;
  quote: string;
}

export const useNotesStore = defineStore("notes", {
  state: () => ({
    notes: [] as Note[],
    loaded: false,
    editing: null as Note | null, // note currently open in the editor
  }),
  getters: {
    forChapter: (state) => (slug: string) =>
      state.notes
        .filter((n) => n.chapter === slug)
        .sort((a, b) => a.createdAt - b.createdAt),
    countFor: (state) => (slug: string) => state.notes.filter((n) => n.chapter === slug).length,
    ordered: (state) => [...state.notes].sort((a, b) => b.updatedAt - a.updatedAt),
  },
  actions: {
    async load() {
      // notes live in the cloud (Firestore) and require sign-in; reading is open.
      if (!useAuthStore().signedIn) {
        this.notes = [];
        this.loaded = true;
        return;
      }
      try {
        this.notes = await storage.listNotes();
      } catch {
        this.notes = [];
      }
      this.loaded = true;
    },
    clear() {
      this.notes = [];
      this.editing = null;
    },
    startDraft(d: DraftNote) {
      const now = Date.now();
      this.editing = {
        id: newId(),
        color: "sun",
        body: "",
        createdAt: now,
        updatedAt: now,
        ...d,
      };
    },
    edit(note: Note) {
      this.editing = { ...note };
    },
    cancel() {
      this.editing = null;
    },
    async commit(body: string, color: string) {
      if (!this.editing) return;
      const note: Note = { ...this.editing, body: body.trim(), color, updatedAt: Date.now() };
      const i = this.notes.findIndex((n) => n.id === note.id);
      if (i >= 0) this.notes[i] = note;
      else this.notes.push(note);
      this.editing = null;
      await storage.saveNote(note);
    },
    async remove(id: string) {
      this.notes = this.notes.filter((n) => n.id !== id);
      if (this.editing?.id === id) this.editing = null;
      await storage.deleteNote(id);
    },
  },
});
