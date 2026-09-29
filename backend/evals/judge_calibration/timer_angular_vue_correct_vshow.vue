<template>
  <div class="session-timer">
    <h2>{{ label }}</h2>
    <p class="time">{{ formatted }}</p>
    <p v-show="!notExpired" class="warning">Time's up!</p>
    <button @click="reset">Reset</button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  label: { type: String, default: 'Session' },
  limit: { type: Number, default: 60 },
})

const seconds = ref(0)
let intervalId

const formatted = computed(() => {
  const m = String(Math.floor(seconds.value / 60)).padStart(2, '0')
  const s = String(seconds.value % 60).padStart(2, '0')
  return `${m}:${s}`
})

const notExpired = computed(() => seconds.value < props.limit)

function reset() {
  seconds.value = 0
}

onMounted(() => {
  intervalId = setInterval(() => {
    seconds.value++
  }, 1000)
})

onUnmounted(() => {
  clearInterval(intervalId)
})
</script>
