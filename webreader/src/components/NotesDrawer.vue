<script setup lang="ts">
import { ref, watch, computed, nextTick } from "vue";
import { useAppStore } from "../stores/app";
import { useNotesStore } from "../stores/notes";
import { useAuthStore } from "../stores/auth";
import type { Note } from "../lib/storage";

const app = useAppStore();
const notes = useNotesStore();
const auth = useAuthStore();

const COLORS = ["sun", "teal", "rose", "sky"] as const;
const body = ref("");
const color = ref<string>("sun");
const editorEl = ref<HTMLTextAreaElement | null>(null);
const showAll = ref(false);

watch(
  () => notes.editing,
  async (e) => {
    if (e) {
      body.value = e.body;
      color.value = e.color;
      app.notesOpen = true;
      await nextTick();
      editorEl.value?.focus();
    }
  }
);

const visible = computed<Note[]>(() =>
  showAll.value ? notes.ordered : notes.forChapter(app.currentSlug)
);

function save() {
  void notes.commit(body.value, color.value);
}

// add a typed note without needing a text selection — anchor to the heading
// currently in view (scroll-spy), so this works fine on a tablet / with a stylus.
function addHere() {
  if (!app.current) return;
  const h = app.headings.find((x) => x.id === app.activeHeading);
  notes.startDraft({
    chapter: app.currentSlug,
    chapterTitle: app.current.title,
    anchor: h?.id || "",
    anchorText: h?.text || app.current.label,
    quote: "",
  });
}

function fmt(ts: number): string {
  return new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
</script>

<template>
  <aside class="notes">
    <div class="notes-head">
      <div class="tabs">
        <button :class="{ on: !showAll }" @click="showAll = false">This chapter</button>
        <button :class="{ on: showAll }" @click="showAll = true">All ({{ notes.notes.length }})</button>
      </div>
      <button
        v-if="auth.signedIn && !notes.editing"
        class="addbtn"
        title="Add a note here"
        @click="addHere"
      >＋ Note</button>
      <button class="x" @click="app.notesOpen = false">✕</button>
    </div>

    <!-- signed-out gate: reading is open, notes need an account -->
    <div v-if="auth.ready && !auth.signedIn" class="gate">
      <p>Your notes sync to your account and are readable from any Claude session
        (via <code>econ notes</code>). Sign in to start.</p>
      <button class="btn solid" @click="auth.signIn()">Sign in with Google</button>
      <p v-if="auth.error" class="err">{{ auth.error }}</p>
    </div>

    <!-- editor -->
    <div v-else-if="notes.editing" class="editor">
      <div class="q">“{{ notes.editing.quote }}”</div>
      <div v-if="notes.editing.anchorText" class="anchor">↳ {{ notes.editing.anchorText }}</div>
      <textarea
        ref="editorEl"
        v-model="body"
        rows="4"
        placeholder="Your note…"
        @keydown.meta.enter="save"
        @keydown.ctrl.enter="save"
      ></textarea>
      <div class="row">
        <div class="chips">
          <button
            v-for="c in COLORS"
            :key="c"
            class="chip"
            :class="[c, { on: color === c }]"
            @click="color = c"
          ></button>
        </div>
        <div class="grow"></div>
        <button class="btn ghost" @click="notes.cancel()">Cancel</button>
        <button class="btn solid" @click="save">Save</button>
      </div>
    </div>

    <!-- list -->
    <div v-if="auth.signedIn" class="list">
      <p v-if="!visible.length && !notes.editing" class="empty">
        Select any text in the report to attach a note. Notes are saved on this device (M1) —
        they'll sync to your account once the cloud store is wired.
      </p>
      <article v-for="n in visible" :key="n.id" class="note" :class="n.color">
        <button class="quote" @click="app.jumpTo(n.chapter, n.anchor)">“{{ n.quote }}”</button>
        <div v-if="n.body" class="body">{{ n.body }}</div>
        <div class="meta">
          <span v-if="showAll" class="where">{{ n.anchorText || n.chapter }}</span>
          <span class="date">{{ fmt(n.updatedAt) }}</span>
          <span class="grow"></span>
          <button class="mini" @click="notes.edit(n)">Edit</button>
          <button class="mini danger" @click="notes.remove(n.id)">Delete</button>
        </div>
      </article>
    </div>
  </aside>
</template>

<style scoped>
.notes {
  grid-area: notes; background: var(--surface); border-left: 1px solid var(--line);
  display: flex; flex-direction: column; overflow: hidden;
}
.notes-head {
  display: flex; align-items: center; gap: 0.5rem; padding: 0.6rem 0.7rem;
  border-bottom: 1px solid var(--line);
}
.tabs { display: flex; gap: 2px; background: var(--surface-2); border-radius: 8px; padding: 2px; }
.tabs button {
  border: none; background: transparent; color: var(--ink-soft); font-size: 0.8rem;
  padding: 0.3rem 0.6rem; border-radius: 6px;
}
.tabs button.on { background: var(--surface); color: var(--ink); font-weight: 600; box-shadow: var(--shadow); }
.addbtn {
  margin-left: auto; border: 1px solid var(--line); background: var(--surface-2);
  color: var(--ink); font-size: 0.78rem; font-weight: 600; padding: 0.28rem 0.55rem;
  border-radius: 8px;
}
.addbtn:hover { border-color: var(--accent); color: var(--accent); }
.x { border: none; background: transparent; color: var(--ink-faint); font-size: 1rem; }

.gate { padding: 1.1rem 0.9rem; display: flex; flex-direction: column; gap: 0.7rem; }
.gate p { margin: 0; font-size: 0.85rem; color: var(--ink-soft); line-height: 1.5; }
.gate code { font-size: 0.8em; background: var(--surface-2); padding: 0.05em 0.3em; border-radius: 4px; }
.gate .err { color: var(--danger); font-size: 0.78rem; }
.editor { padding: 0.7rem; border-bottom: 1px solid var(--line); background: var(--surface-2); }
.q { font-family: var(--serif); font-size: 0.9rem; color: var(--ink-soft); margin-bottom: 0.3rem; }
.anchor { font-size: 0.72rem; color: var(--ink-faint); margin-bottom: 0.4rem; }
textarea {
  width: 100%; resize: vertical; border: 1px solid var(--line); border-radius: 8px;
  background: var(--surface); color: var(--ink); font-family: var(--sans);
  font-size: 0.92rem; padding: 0.5rem; line-height: 1.4;
}
.row { display: flex; align-items: center; gap: 0.4rem; margin-top: 0.5rem; }
.grow { flex: 1; }
.chips { display: flex; gap: 4px; }
.chip { width: 18px; height: 18px; border-radius: 50%; border: 2px solid transparent; }
.chip.on { border-color: var(--ink); }
.chip.sun { background: #e8b23a; } .chip.teal { background: #0d6e78; }
.chip.rose { background: #b4457a; } .chip.sky { background: #3b73b4; }
.btn { border: none; border-radius: 8px; padding: 0.4rem 0.8rem; font-size: 0.85rem; }
.btn.ghost { background: transparent; color: var(--ink-soft); }
.btn.solid { background: var(--accent); color: #fff; font-weight: 600; }

.list { overflow-y: auto; padding: 0.6rem; display: flex; flex-direction: column; gap: 0.6rem; }
.empty { color: var(--ink-faint); font-size: 0.85rem; line-height: 1.5; padding: 0.4rem; }
.note {
  background: var(--surface-2); border-radius: 10px; padding: 0.55rem 0.6rem;
  border-left: 3px solid var(--ink-faint);
}
.note.sun { border-left-color: #e8b23a; } .note.teal { border-left-color: #0d6e78; }
.note.rose { border-left-color: #b4457a; } .note.sky { border-left-color: #3b73b4; }
.quote {
  display: block; text-align: left; width: 100%; background: transparent; border: none;
  font-family: var(--serif); font-size: 0.86rem; color: var(--ink-soft); line-height: 1.35;
  padding: 0; cursor: pointer;
}
.quote:hover { color: var(--accent); }
.body { font-size: 0.9rem; color: var(--ink); margin-top: 0.35rem; white-space: pre-wrap; }
.meta { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.4rem; font-size: 0.72rem; color: var(--ink-faint); }
.where { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 40%; }
.mini { border: none; background: transparent; color: var(--ink-faint); font-size: 0.72rem; }
.mini:hover { color: var(--ink); } .mini.danger:hover { color: var(--danger); }

@media (max-width: 1100px) {
  .notes {
    position: fixed; z-index: 35; top: 56px; bottom: 0; right: 0; width: 340px; max-width: 88vw;
    transform: translateX(102%); transition: transform 0.22s ease; box-shadow: var(--shadow);
  }
  :global(.shell.notes-open) .notes { transform: translateX(0); }
}
</style>
