import { doc, getDoc, setDoc } from "firebase/firestore";
import { db, auth } from "./firebase";

// A handwritten stroke. Points are stored NORMALIZED by the reading-column width
// (nx = x/colWidth, ny = y/colWidth) so ink re-aligns when the column reflows or
// the device changes — render by multiplying back up by the current column width.
export interface InkStroke {
  c: string; // color
  w: number; // base width (px at capture)
  p: number[]; // flat [nx0, ny0, nx1, ny1, ...]
}

const COLL = "ink";

export async function loadInk(chapter: string): Promise<InkStroke[]> {
  try {
    const snap = await getDoc(doc(db, COLL, chapter));
    return snap.exists() ? ((snap.data().strokes as InkStroke[]) || []) : [];
  } catch {
    return [];
  }
}

export async function saveInk(chapter: string, strokes: InkStroke[]): Promise<void> {
  await setDoc(doc(db, COLL, chapter), {
    chapter,
    strokes,
    owner: auth.currentUser?.uid || "",
    email: auth.currentUser?.email || "",
    updatedAt: Date.now(),
  });
}
