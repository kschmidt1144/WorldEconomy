<script setup lang="ts">
import { useAppStore } from "../stores/app";
import { useNotesStore } from "../stores/notes";
import { useAuthStore } from "../stores/auth";

const app = useAppStore();
const notes = useNotesStore();
const auth = useAuthStore();
</script>

<template>
  <header class="hdr">
    <button class="icon side-toggle" title="Chapters" @click="app.sidebarOpen = !app.sidebarOpen; app.notesOpen = false">☰</button>
    <div class="brand">
      <span class="mark">◆</span>
      <span class="title">World&nbsp;Economy&nbsp;Lab</span>
      <span class="chap" v-if="app.current">· {{ app.current.label }}</span>
    </div>
    <div class="spacer"></div>
    <button
      v-if="auth.ready && !auth.signedIn"
      class="signin"
      title="Sign in to sync notes"
      @click="auth.signIn()"
    >
      Sign in
    </button>
    <img
      v-else-if="auth.signedIn && auth.photo"
      class="avatar"
      :src="auth.photo"
      :title="`${auth.displayName} — sign out`"
      referrerpolicy="no-referrer"
      @click="auth.signOut()"
    />
    <button class="icon" :title="app.theme === 'dark' ? 'Light mode' : 'Dark mode'" @click="app.toggleTheme()">
      {{ app.theme === "dark" ? "☀" : "☾" }}
    </button>
    <button class="icon notes-toggle" title="Notes" @click="app.notesOpen = !app.notesOpen; app.sidebarOpen = false">
      ✎<span v-if="notes.notes.length" class="badge">{{ notes.notes.length }}</span>
    </button>
  </header>
</template>

<style scoped>
.hdr {
  grid-area: head; display: flex; align-items: center; gap: 0.5rem;
  padding: 0 0.75rem; background: var(--accent-deep); color: #eaf3f2;
  position: sticky; top: 0; z-index: 40;
}
.brand { display: flex; align-items: baseline; gap: 0.4rem; min-width: 0; }
.mark { color: var(--sun); }
.title { font-weight: 600; letter-spacing: 0.01em; white-space: nowrap; }
.chap { color: #a9c6cb; font-size: 0.9rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.spacer { flex: 1; }
.icon {
  position: relative; background: transparent; border: none; color: #eaf3f2;
  font-size: 1.15rem; width: 40px; height: 40px; border-radius: 8px;
}
.icon:hover { background: rgba(255, 255, 255, 0.12); }
.badge {
  position: absolute; top: 3px; right: 2px; background: var(--sun); color: #3a2c05;
  font-size: 0.62rem; font-weight: 700; min-width: 15px; height: 15px; border-radius: 8px;
  display: grid; place-items: center; padding: 0 3px;
}
.signin {
  background: var(--sun); color: #3a2c05; border: none; font-weight: 600;
  font-size: 0.82rem; padding: 0.35rem 0.7rem; border-radius: 8px;
}
.signin:hover { filter: brightness(1.05); }
.avatar { width: 30px; height: 30px; border-radius: 50%; cursor: pointer; border: 1px solid rgba(255,255,255,0.3); }
.side-toggle, .notes-toggle { display: none; }
@media (max-width: 1100px) {
  .side-toggle, .notes-toggle { display: inline-flex; align-items: center; justify-content: center; }
}
@media (max-width: 640px) { .title { display: none; } }
</style>
