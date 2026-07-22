<script setup lang="ts">
import { useInkStore, INK_COLORS } from "../stores/ink";
import { useAuthStore } from "../stores/auth";

const ink = useInkStore();
const auth = useAuthStore();

async function penTap() {
  if (!auth.signedIn) {
    await auth.signIn();
    return;
  }
  ink.enter();
}
</script>

<template>
  <!-- pen FAB (reading mode) -->
  <button
    v-if="!ink.active"
    class="fab"
    :title="auth.signedIn ? 'Write with stylus' : 'Sign in to write'"
    @click="penTap"
  >
    ✎
  </button>

  <!-- ink toolbar (ink mode) -->
  <div v-else class="bar">
    <div class="colors">
      <button
        v-for="c in INK_COLORS"
        :key="c"
        class="swatch"
        :class="{ on: ink.mode === 'draw' && ink.color === c }"
        :style="{ background: c }"
        @click="ink.setColor(c)"
      ></button>
    </div>
    <span class="sep"></span>
    <button class="tool" :class="{ on: ink.mode === 'erase' }" title="Eraser" @click="ink.setMode('erase')">⌫</button>
    <button class="tool" title="Undo" :disabled="!ink.hasInk" @click="ink.undo()">↺</button>
    <button class="tool" title="Clear page" :disabled="!ink.hasInk" @click="ink.clear()">🗑</button>
    <button
      class="tool"
      :class="{ on: ink.allowTouch }"
      :title="ink.allowTouch ? 'Finger draws (tap to let finger scroll)' : 'Finger scrolls (tap to draw with finger)'"
      @click="ink.allowTouch = !ink.allowTouch"
    >✋</button>
    <span class="sep"></span>
    <span v-if="ink.saving" class="saving">saving…</span>
    <button class="done" @click="ink.exit()">Done</button>
  </div>
</template>

<style scoped>
.fab {
  position: fixed; z-index: 45; right: 18px; bottom: 20px;
  width: 52px; height: 52px; border-radius: 50%; border: none;
  background: var(--accent-deep); color: var(--sun); font-size: 1.4rem;
  box-shadow: var(--shadow); display: grid; place-items: center;
}
.fab:hover { filter: brightness(1.12); }

.bar {
  position: fixed; z-index: 45; left: 50%; bottom: 18px; transform: translateX(-50%);
  display: flex; align-items: center; gap: 0.4rem; max-width: 94vw;
  background: var(--surface); border: 1px solid var(--line); border-radius: 999px;
  padding: 0.4rem 0.6rem; box-shadow: var(--shadow);
}
.colors { display: flex; gap: 4px; }
.swatch {
  width: 22px; height: 22px; border-radius: 50%; border: 2px solid var(--line);
}
.swatch.on { border-color: var(--ink); transform: scale(1.12); }
.sep { width: 1px; height: 22px; background: var(--line); }
.tool {
  background: transparent; border: none; color: var(--ink-soft);
  font-size: 1.05rem; width: 34px; height: 34px; border-radius: 8px;
}
.tool:hover:not(:disabled) { background: var(--surface-2); color: var(--ink); }
.tool.on { background: var(--sun-soft); color: var(--accent-deep); }
.tool:disabled { opacity: 0.35; }
.saving { font-size: 0.72rem; color: var(--ink-faint); }
.done {
  background: var(--accent); color: #fff; border: none; font-weight: 600;
  font-size: 0.85rem; padding: 0.4rem 0.9rem; border-radius: 999px;
}
@media (max-width: 480px) {
  .tool { width: 30px; height: 30px; font-size: 0.98rem; }
  .swatch { width: 20px; height: 20px; }
}
</style>
