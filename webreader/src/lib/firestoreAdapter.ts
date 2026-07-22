import { collection, deleteDoc, doc, getDocs, setDoc } from "firebase/firestore";
import { db, auth } from "./firebase";
import type { Note, Progress, StorageAdapter } from "./storage";

// Notes sync to Firestore `worldeconomy/notes` (read back by the econlab MCP).
// Reading position (progress) is device-local — it stays in localStorage.
const PROGRESS_KEY = "we-reader:progress";
const NOTES = "notes";

export class FirestoreAdapter implements StorageAdapter {
  readonly kind = "firestore";

  async listNotes(): Promise<Note[]> {
    const snap = await getDocs(collection(db, NOTES));
    return snap.docs.map((d) => d.data() as Note);
  }

  async saveNote(note: Note): Promise<void> {
    await setDoc(doc(db, NOTES, note.id), {
      ...note,
      owner: auth.currentUser?.uid || "",
      email: auth.currentUser?.email || "",
      source: "web",
    });
  }

  async deleteNote(id: string): Promise<void> {
    await deleteDoc(doc(db, NOTES, id));
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
