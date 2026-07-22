<script setup lang="ts">
import { useAppStore } from "../stores/app";
import { useNotesStore } from "../stores/notes";

const app = useAppStore();
const notes = useNotesStore();

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  app.sidebarOpen = false;
}
</script>

<template>
  <aside class="side" :class="{ open: app.sidebarOpen }">
    <div class="side-scroll">
      <div class="eyebrow">Chapters</div>
      <nav class="chapters">
        <button
          v-for="c in app.chapters"
          :key="c.slug"
          class="chap-row"
          :class="{ active: c.slug === app.currentSlug }"
          @click="app.goto(c.slug)"
        >
          <span class="num">{{ String(c.num).padStart(2, "0") }}</span>
          <span class="lbl">{{ c.label }}</span>
          <span v-if="notes.countFor(c.slug)" class="ncount">{{ notes.countFor(c.slug) }}</span>
        </button>
      </nav>

      <template v-if="app.headings.length">
        <div class="eyebrow">On this page</div>
        <nav class="outline">
          <button
            v-for="h in app.headings"
            :key="h.id"
            class="out-row"
            :class="{ sub: h.level === 3, active: h.id === app.activeHeading }"
            @click="scrollTo(h.id)"
          >
            {{ h.text }}
          </button>
        </nav>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.side {
  grid-area: side; background: var(--surface); border-right: 1px solid var(--line);
  overflow: hidden; display: flex; flex-direction: column;
}
.side-scroll { overflow-y: auto; padding: 1rem 0.6rem 3rem; }
.eyebrow {
  font-size: 0.68rem; letter-spacing: 0.09em; text-transform: uppercase;
  color: var(--ink-faint); margin: 1rem 0.6rem 0.4rem; font-weight: 600;
}
.chapters, .outline { display: flex; flex-direction: column; gap: 1px; }
.chap-row {
  display: flex; align-items: baseline; gap: 0.55rem; text-align: left;
  background: transparent; border: none; color: var(--ink-soft);
  padding: 0.42rem 0.6rem; border-radius: 8px; font-size: 0.92rem; width: 100%;
}
.chap-row:hover { background: var(--surface-2); color: var(--ink); }
.chap-row.active { background: var(--surface-2); color: var(--ink); font-weight: 600; }
.chap-row .num { color: var(--ink-faint); font-variant-numeric: tabular-nums; font-size: 0.8rem; }
.chap-row .lbl { flex: 1; }
.ncount {
  background: var(--sun-soft); color: var(--accent-deep); font-size: 0.68rem;
  border-radius: 8px; padding: 0 0.4rem; font-weight: 700;
}
.out-row {
  text-align: left; background: transparent; border: none; color: var(--ink-faint);
  padding: 0.28rem 0.6rem; border-radius: 6px; font-size: 0.85rem; width: 100%;
  border-left: 2px solid transparent; line-height: 1.3;
}
.out-row.sub { padding-left: 1.4rem; font-size: 0.8rem; }
.out-row:hover { color: var(--ink); }
.out-row.active { color: var(--accent); border-left-color: var(--accent); }

@media (max-width: 1100px) {
  .side {
    position: fixed; z-index: 35; top: 56px; bottom: 0; left: 0; width: 300px;
    transform: translateX(-102%); transition: transform 0.22s ease; box-shadow: var(--shadow);
  }
  .side.open { transform: translateX(0); }
}
</style>
