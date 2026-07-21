// Storage abstraction. M1 ships LocalStorageAdapter; M2 swaps a FirestoreAdapter
// with the SAME interface (named DB `worldeconomy`), and the econlab MCP reads it back.

export interface Note {
  id: string;
  chapter: string; // chapter slug, e.g. "10-chokepoints"
  chapterTitle: string;
  anchor: string; // element id in the chapter (heading or figure), may be ""
  anchorText: string; // human label for the anchor
  quote: string; // the selected text
  body: string; // the user's note
  color: string; // highlight color key
  createdAt: number;
  updatedAt: number;
}

export interface Progress {
  chapter: string;
  ratio: number; // 0..1 scroll position within the chapter
  updatedAt: number;
}

export interface StorageAdapter {
  readonly kind: string;
  listNotes(): Promise<Note[]>;
  saveNote(note: Note): Promise<void>;
  deleteNote(id: string): Promise<void>;
  getProgress(): Promise<Progress | null>;
  setProgress(p: Progress): Promise<void>;
}

const NOTES_KEY = "we-reader:notes";
const PROGRESS_KEY = "we-reader:progress";

export class LocalStorageAdapter implements StorageAdapter {
  readonly kind = "local";

  async listNotes(): Promise<Note[]> {
    try {
      return JSON.parse(localStorage.getItem(NOTES_KEY) || "[]") as Note[];
    } catch {
      return [];
    }
  }

  private async writeAll(notes: Note[]): Promise<void> {
    localStorage.setItem(NOTES_KEY, JSON.stringify(notes));
  }

  async saveNote(note: Note): Promise<void> {
    const all = await this.listNotes();
    const i = all.findIndex((n) => n.id === note.id);
    if (i >= 0) all[i] = note;
    else all.push(note);
    await this.writeAll(all);
  }

  async deleteNote(id: string): Promise<void> {
    await this.writeAll((await this.listNotes()).filter((n) => n.id !== id));
  }

  async getProgress(): Promise<Progress | null> {
    try {
      const raw = localStorage.getItem(PROGRESS_KEY);
      return raw ? (JSON.parse(raw) as Progress) : null;
    } catch {
      return null;
    }
  }

  async setProgress(p: Progress): Promise<void> {
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(p));
  }
}

export function newId(): string {
  return "n_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

// The single adapter instance the app uses. Swap this line in M2 for FirestoreAdapter.
export const storage: StorageAdapter = new LocalStorageAdapter();
