<template>
  <div class="counter">
    <h2>Count: {{ count }}</h2>
    <p>{{ isEven ? 'Even' : 'Odd' }}</p>
    <button @click="decrement">-</button>
    <button @click="increment">+</button>
    <button @click="reset">Reset</button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  initial: { type: Number, default: 0 },
  step: { type: Number, default: 1 },
})

const count = ref(props.initial)
const isEven = computed(() => count.value % 2 === 0)

const increment = () => {
  count.value += props.step
}

const decrement = () => {
  count.value -= props.step
}

const reset = () => {
  count.value = props.initial
}
</script>
