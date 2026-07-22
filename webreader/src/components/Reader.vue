<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { useAppStore } from "../stores/app";
import { useNotesStore } from "../stores/notes";
import { useAuthStore } from "../stores/auth";
import { loadChapterHtml, hydrateContent, anchorAtY } from "../lib/report";
import SelectionPopover from "./SelectionPopover.vue";
import InkLayer from "./InkLayer.vue";

const app = useAppStore();
const notes = useNotesStore();
const auth = useAuthStore();

const contentEl = ref<HTMLElement | null>(null);
const html = ref("");
const loading = ref(false);

let scrollEl: HTMLElement | null = null;
let observer: IntersectionObserver | null = null;
let rafPending = false;

const pop = ref({ show: false, x: 0, y: 0, quote: "", anchor: "", anchorText: "" });

async function render(slug: string, restoreRatio: number | null) {
  loading.value = true;
  pop.value.show = false;
  html.value = await loadChapterHtml(slug);
  await nextTick();
  const root = contentEl.value;
  if (!root) return;
  const headings = hydrateContent(root);
  app.headings = headings;
  app.activeHeading = headings[0]?.id || "";
  setupSpy(headings.map((h) => h.id));
  loading.value = false;
  await nextTick();
  if (app.pendingAnchor) {
    flashTo(app.pendingAnchor);
    app.pendingAnchor = "";
  } else if (scrollEl) {
    const max = scrollEl.scrollHeight - scrollEl.clientHeight;
    scrollEl.scrollTop = restoreRatio && max > 0 ? restoreRatio * max : 0;
  }
}

function flashTo(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
  el.classList.add("flash");
  window.setTimeout(() => el.classList.remove("flash"), 1400);
}

function setupSpy(ids: string[]) {
  observer?.disconnect();
  if (!scrollEl || !ids.length) return;
  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible[0]) app.activeHeading = (visible[0].target as HTMLElement).id;
    },
    { root: scrollEl, rootMargin: "-72px 0px -70% 0px", threshold: 0 }
  );
  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (el) observer!.observe(el);
  });
}

function onScroll() {
  pop.value.show = false;
  if (rafPending || !scrollEl) return;
  rafPending = true;
  requestAnimationFrame(() => {
    rafPending = false;
    if (!scrollEl) return;
    const max = scrollEl.scrollHeight - scrollEl.clientHeight;
    app.saveProgress(max > 0 ? scrollEl.scrollTop / max : 0);
  });
}

function onSelect() {
  const sel = window.getSelection();
  const root = contentEl.value;
  if (!sel || sel.isCollapsed || !root) return (pop.value.show = false);
  const quote = sel.toString().trim();
  if (quote.length < 2 || !root.contains(sel.anchorNode)) return (pop.value.show = false);
  const rect = sel.getRangeAt(0).getBoundingClientRect();
  const a = anchorAtY(root, rect.top);
  pop.value = {
    show: true,
    x: Math.min(Math.max(rect.left + rect.width / 2, 90), window.innerWidth - 90),
    y: rect.top - 8,
    quote: quote.length > 600 ? quote.slice(0, 600) + "…" : quote,
    anchor: a.id,
    anchorText: a.text,
  };
}

function addNote() {
  if (!app.current) return;
  // notes require an account; open the drawer's sign-in gate if needed
  if (!auth.signedIn) {
    app.notesOpen = true;
    pop.value.show = false;
    return;
  }
  notes.startDraft({
    chapter: app.currentSlug,
    chapterTitle: app.current.title,
    anchor: pop.value.anchor,
    anchorText: pop.value.anchorText,
    quote: pop.value.quote,
  });
  app.notesOpen = true;
  pop.value.show = false;
  window.getSelection()?.removeAllRanges();
}

onMounted(() => {
  scrollEl = contentEl.value?.closest(".main") as HTMLElement | null;
  scrollEl?.addEventListener("scroll", onScroll, { passive: true });
  document.addEventListener("selectionchange", onSelect);
  if (app.currentSlug) {
    const r = app.resume && app.resume.chapter === app.currentSlug ? app.resume.ratio : null;
    render(app.currentSlug, r);
  }
});

onBeforeUnmount(() => {
  scrollEl?.removeEventListener("scroll", onScroll);
  document.removeEventListener("selectionchange", onSelect);
  observer?.disconnect();
});

watch(
  () => app.currentSlug,
  (slug, prev) => {
    if (slug && slug !== prev) render(slug, null);
  }
);

// same-chapter jump (chapter didn't change, so render() won't fire)
watch(
  () => app.pendingAnchor,
  (id) => {
    if (id && !loading.value) {
      flashTo(id);
      app.pendingAnchor = "";
    }
  }
);
</script>

<template>
  <article class="reader">
    <InkLayer />
    <div ref="contentEl" class="prose" v-html="html"></div>

    <nav class="chap-nav" v-if="app.current">
      <button v-if="app.currentIndex > 0" class="pn prev" @click="app.nav(-1)">
        ‹ {{ app.chapters[app.currentIndex - 1].label }}
      </button>
      <span class="spacer"></span>
      <button
        v-if="app.currentIndex < app.chapters.length - 1"
        class="pn next"
        @click="app.nav(1)"
      >
        {{ app.chapters[app.currentIndex + 1].label }} ›
      </button>
    </nav>

    <SelectionPopover
      :show="pop.show"
      :x="pop.x"
      :y="pop.y"
      @note="addNote"
      @dismiss="pop.show = false"
    />
  </article>
</template>

<style scoped>
.reader { position: relative; max-width: var(--measure); margin: 0 auto; padding: 2rem 1.4rem 6rem; }
.chap-nav { display: flex; align-items: center; gap: 1rem; margin-top: 3rem; padding-top: 1.2rem; border-top: 1px solid var(--line); }
.spacer { flex: 1; }
.pn {
  background: var(--surface); border: 1px solid var(--line); color: var(--ink-soft);
  padding: 0.55rem 0.9rem; border-radius: 10px; font-size: 0.9rem; max-width: 46%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pn:hover { color: var(--ink); border-color: var(--accent); }
@media (max-width: 640px) { .reader { padding: 1.3rem 1.05rem 5rem; } }
</style>
