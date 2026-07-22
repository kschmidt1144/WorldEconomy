import { defineStore } from "pinia";
import { auth } from "../lib/firebase";
import { GoogleAuthProvider, onAuthStateChanged, signInWithPopup, signOut, type User } from "firebase/auth";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null as User | null,
    ready: false, // initial auth state resolved
    error: "" as string,
  }),
  getters: {
    signedIn: (s) => !!s.user,
    displayName: (s) => s.user?.displayName || s.user?.email || "",
    photo: (s) => s.user?.photoURL || "",
  },
  actions: {
    watch() {
      onAuthStateChanged(auth, (u) => {
        this.user = u;
        this.ready = true;
      });
    },
    async signIn() {
      this.error = "";
      try {
        await signInWithPopup(auth, new GoogleAuthProvider());
      } catch (e: any) {
        this.error = e?.message || "sign-in failed";
      }
    },
    async signOut() {
      await signOut(auth);
    },
  },
});
