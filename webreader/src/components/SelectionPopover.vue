<script setup lang="ts">
defineProps<{ show: boolean; x: number; y: number }>();
defineEmits<{ note: []; dismiss: [] }>();
</script>

<template>
  <transition name="pop">
    <div
      v-if="show"
      class="popover"
      :style="{ left: x + 'px', top: y + 'px' }"
      @mousedown.prevent
    >
      <button class="act" @click="$emit('note')">✎ Add note</button>
    </div>
  </transition>
</template>

<style scoped>
.popover {
  position: fixed; z-index: 50; transform: translate(-50%, -100%);
  background: var(--accent-deep); color: #eaf3f2; border-radius: 10px;
  box-shadow: var(--shadow); padding: 3px; display: flex; gap: 2px;
}
.popover::after {
  content: ""; position: absolute; left: 50%; bottom: -5px; transform: translateX(-50%);
  border: 6px solid transparent; border-top-color: var(--accent-deep); border-bottom: 0;
}
.act {
  background: transparent; border: none; color: inherit; font-size: 0.86rem;
  padding: 0.4rem 0.7rem; border-radius: 8px;
}
.act:hover { background: rgba(255, 255, 255, 0.14); }
.pop-enter-active { transition: opacity 0.12s ease, transform 0.12s ease; }
.pop-enter-from { opacity: 0; transform: translate(-50%, -90%); }
</style>
