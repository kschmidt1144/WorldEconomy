<script setup lang="ts">
import { onMounted, watch } from "vue";
import { useAppStore } from "./stores/app";
import { useNotesStore } from "./stores/notes";
import { useAuthStore } from "./stores/auth";
import { useInkStore } from "./stores/ink";
import AppHeader from "./components/AppHeader.vue";
import Sidebar from "./components/Sidebar.vue";
import Reader from "./components/Reader.vue";
import NotesDrawer from "./components/NotesDrawer.vue";
import InkControls from "./components/InkControls.vue";

const app = useAppStore();
const notes = useNotesStore();
const auth = useAuthStore();
const ink = useInkStore();

onMounted(() => {
  app.init(); // reader works immediately, no auth needed
  auth.watch();
  // dev-only test hook (statically stripped from production builds)
  if (import.meta.env.DEV) (window as any).__ink = ink;
});

// (re)load notes + ink whenever sign-in state settles/changes
watch(
  () => [auth.ready, auth.signedIn],
  () => {
    if (!auth.ready) return;
    if (auth.signedIn) {
      notes.load();
      if (app.currentSlug) ink.loadFor(app.currentSlug);
    } else {
      notes.clear();
      ink.exit();
      ink.strokes = [];
    }
  },
  { immediate: true }
);

// load this chapter's ink when the chapter changes
watch(
  () => app.currentSlug,
  (slug) => {
    if (slug && auth.signedIn) ink.loadFor(slug);
  }
);
</script>

<template>
  <div class="shell" :class="{ 'sidebar-open': app.sidebarOpen, 'notes-open': app.notesOpen }">
    <AppHeader />
    <Sidebar />
    <main class="main">
      <Reader v-if="app.loaded" />
      <div v-else class="loading">Loading the report…</div>
    </main>
    <NotesDrawer />
    <InkControls />
    <div
      v-if="app.sidebarOpen || app.notesOpen"
      class="scrim"
      @click="app.sidebarOpen = false; app.notesOpen = false"
    ></div>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 300px 1fr 340px;
  grid-template-rows: 56px 1fr;
  grid-template-areas: "head head head" "side main notes";
  height: 100%;
}
.main {
  grid-area: main;
  overflow-y: auto;
  scroll-behavior: smooth;
}
.loading { padding: 3rem; color: var(--ink-faint); }
.scrim { display: none; }

/* Tablet / phone: sidebar + notes become slide-over drawers */
@media (max-width: 1100px) {
  .shell { grid-template-columns: 1fr; grid-template-areas: "head" "main"; }
  .scrim {
    display: block; position: fixed; inset: 56px 0 0 0; z-index: 30;
    background: rgba(10, 16, 20, 0.42);
  }
}
</style>
