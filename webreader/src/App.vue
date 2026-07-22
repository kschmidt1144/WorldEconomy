<script setup lang="ts">
import { onMounted, watch } from "vue";
import { useAppStore } from "./stores/app";
import { useNotesStore } from "./stores/notes";
import { useAuthStore } from "./stores/auth";
import AppHeader from "./components/AppHeader.vue";
import Sidebar from "./components/Sidebar.vue";
import Reader from "./components/Reader.vue";
import NotesDrawer from "./components/NotesDrawer.vue";

const app = useAppStore();
const notes = useNotesStore();
const auth = useAuthStore();

onMounted(() => {
  app.init(); // reader works immediately, no auth needed
  auth.watch();
});

// (re)load notes whenever sign-in state settles/changes
watch(
  () => [auth.ready, auth.signedIn],
  () => {
    if (auth.ready) auth.signedIn ? notes.load() : notes.clear();
  },
  { immediate: true }
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
