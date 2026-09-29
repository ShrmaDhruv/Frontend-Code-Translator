<template>
  <div class="session-timer">
    <h2>Session</h2>
    <p class="time">{{ formatTime(seconds) }}</p>
    <p class="warning" :hidden="seconds < LIMIT">Time's up!</p>
    <button @click="reset">Reset</button>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const LIMIT = 60
const seconds = ref(0)
let intervalId = null

function formatTime(total) {
  const m = String(Math.floor(total / 60)).padStart(2, '0')
  const s = String(total % 60).padStart(2, '0')
  return m + ':' + s
}

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
