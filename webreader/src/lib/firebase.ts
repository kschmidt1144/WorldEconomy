import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import {
  initializeFirestore,
  persistentLocalCache,
  persistentMultipleTabManager,
} from "firebase/firestore";

// Shared Kykli Firebase project (apiKey is a public client identifier, not a secret —
// same config every kykli.dev frontend ships). Notes live in the named `worldeconomy`
// database, read back by the econlab MCP (`econ_notes`).
const firebaseConfig = {
  apiKey: "AIzaSyBVIt8tyAaC8DwPhzsuMB5Pe3b7OLv-KH0",
  authDomain: "kykli-489802.firebaseapp.com",
  projectId: "kykli-489802",
  storageBucket: "kykli-489802.firebasestorage.app",
  messagingSenderId: "1080153322299",
  appId: "1:1080153322299:web:91cd189dc29d36c6f2bd1e",
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

// Named DB + offline persistence so notes can be written on the tablet with no
// connection and sync automatically (Firestore queues offline writes).
export const db = initializeFirestore(
  app,
  { localCache: persistentLocalCache({ tabManager: persistentMultipleTabManager() }) },
  "worldeconomy",
);
