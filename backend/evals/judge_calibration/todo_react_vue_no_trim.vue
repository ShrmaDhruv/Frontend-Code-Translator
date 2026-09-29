<template>
  <div class="todo-list">
    <h2>{{ title }}</h2>
    <input v-model="newTodo" placeholder="What needs doing?" />
    <button @click="addTodo">Add</button>
    <p v-if="todos.length === 0">No todos yet</p>
    <ul v-else>
      <li v-for="todo in todos" :key="todo.id" :class="{ done: todo.done }">
        <input type="checkbox" :checked="todo.done" @change="toggleTodo(todo.id)" />
        <span>{{ todo.text }}</span>
        <button @click="removeTodo(todo.id)">Delete</button>
      </li>
    </ul>
    <p>{{ remaining }} remaining</p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

defineProps({
  title: { type: String, default: 'My Todos' },
})

const todos = ref([])
const newTodo = ref('')
const remaining = computed(() => todos.value.filter(t => !t.done).length)

function addTodo() {
  todos.value = [...todos.value, { id: Date.now(), text: newTodo.value, done: false }]
  newTodo.value = ''
}

function toggleTodo(id) {
  todos.value = todos.value.map(t => (t.id === id ? { ...t, done: !t.done } : t))
}

function removeTodo(id) {
  todos.value = todos.value.filter(t => t.id !== id)
}
</script>

<style scoped>
.done span {
  text-decoration: line-through;
}
</style>
