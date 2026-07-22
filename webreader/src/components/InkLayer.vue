<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { useInkStore } from "../stores/ink";
import { useAppStore } from "../stores/app";

// An SVG overlay that sits INSIDE the reading column (position: absolute over the
// article). Because it's in the content flow it scrolls with the text for free —
// no scroll listeners, no rAF, no giant canvas. Points are stored normalized by the
// column width, so ink re-aligns across reflow / devices.
const ink = useInkStore();
const app = useAppStore();

const svg = ref<SVGSVGElement | null>(null);
const w = ref(1); // current column width in px (render scale)

let drawing = false;
const draft = ref<{ c: string; sw: number; d: string } | null>(null);
let last: [number, number] | null = null; // last px point (for thinning + draft d)
let draftNorm: number[] = [];

function measure() {
  if (svg.value) w.value = svg.value.clientWidth || svg.value.getBoundingClientRect().width || 1;
}

// base gesture policy while ink mode is on: finger scrolls (pan-y) unless the user
// opted into finger-drawing (none). Set imperatively so mid-stroke re-renders (the
// draft path updating) never reset it.
function baseTouch(): string {
  return ink.allowTouch ? "none" : "pan-y";
}
function applyTouch(v: string) {
  if (svg.value) svg.value.style.touchAction = v;
}

function pathD(p: number[]): string {
  let d = "";
  for (let i = 0; i < p.length; i += 2) {
    d += (i === 0 ? "M" : "L") + (p[i] * w.value).toFixed(1) + " " + (p[i + 1] * w.value).toFixed(1);
  }
  return d;
}

const strokePaths = computed(() =>
  ink.strokes.map((s, i) => ({ key: i, c: s.c, sw: s.w, d: pathD(s.p) }))
);

function shouldDraw(e: PointerEvent): boolean {
  if (e.pointerType === "touch") return ink.allowTouch;
  return true; // pen + mouse
}

function local(e: PointerEvent): [number, number] {
  const r = svg.value!.getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
}

function eraseAtEvent(e: PointerEvent) {
  const [x, y] = local(e);
  ink.eraseAt(x / w.value, y / w.value, 16 / w.value);
}

function onDown(e: PointerEvent) {
  if (!ink.active || !shouldDraw(e)) return; // touch falls through → page scrolls
  e.preventDefault();
  try { svg.value!.setPointerCapture(e.pointerId); } catch {}
  applyTouch("none"); // lock scroll for the duration of this pen/mouse stroke
  drawing = true;
  if (ink.mode === "erase") { eraseAtEvent(e); return; }
  const [x, y] = local(e);
  const sw = ink.width * (0.6 + (e.pressure || 0.5) * 0.8);
  draft.value = { c: ink.color, sw, d: `M${x.toFixed(1)} ${y.toFixed(1)}` };
  draftNorm = [x / w.value, y / w.value];
  last = [x, y];
}

function onMove(e: PointerEvent) {
  if (!drawing || !ink.active) return;
  e.preventDefault();
  if (ink.mode === "erase") { eraseAtEvent(e); return; }
  const events = (e as any).getCoalescedEvents ? (e as any).getCoalescedEvents() : [e];
  for (const ev of events.length ? events : [e]) {
    const r = svg.value!.getBoundingClientRect();
    const x = ev.clientX - r.left, y = ev.clientY - r.top;
    if (last) {
      const dx = x - last[0], dy = y - last[1];
      if (dx * dx + dy * dy < 1.44) continue; // thin
    }
    draft.value!.d += `L${x.toFixed(1)} ${y.toFixed(1)}`;
    draftNorm.push(x / w.value, y / w.value);
    last = [x, y];
  }
}

function onUp(e: PointerEvent) {
  if (!drawing) return;
  drawing = false;
  applyTouch(baseTouch());
  try { svg.value!.releasePointerCapture(e.pointerId); } catch {}
  if (ink.mode === "draw" && draft.value && draftNorm.length >= 2) {
    ink.addStroke({ c: draft.value.c, w: draft.value.sw, p: draftNorm });
  }
  draft.value = null;
  draftNorm = [];
  last = null;
}

onMounted(() => {
  nextTick(measure);
  window.addEventListener("resize", measure);
});
onBeforeUnmount(() => window.removeEventListener("resize", measure));
watch(() => app.currentSlug, () => nextTick(measure));
watch(() => ink.active, (on) => { if (on) nextTick(measure); });
watch([() => ink.active, () => ink.allowTouch], () => applyTouch(baseTouch()));
</script>

<template>
  <svg
    ref="svg"
    class="ink"
    :class="{ active: ink.active, erase: ink.mode === 'erase' }"
    @pointerdown="onDown"
    @pointermove="onMove"
    @pointerup="onUp"
    @pointercancel="onUp"
  >
    <path
      v-for="p in strokePaths"
      :key="p.key"
      :d="p.d"
      :stroke="p.c"
      :stroke-width="p.sw"
      fill="none"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <path
      v-if="draft"
      :d="draft.d"
      :stroke="draft.c"
      :stroke-width="draft.sw"
      fill="none"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>

<style scoped>
.ink {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 5;
  overflow: visible;
  touch-action: pan-y;
  pointer-events: none; /* transparent to reading until ink mode is on */
}
.ink.active { pointer-events: auto; cursor: crosshair; }
.ink.active.erase { cursor: cell; }
</style>
