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

<script>
export default {
  name: 'TodoList',
  props: {
    title: { type: String, default: 'My Todos' },
  },
  data() {
    return {
      todos: [],
      newTodo: '',
    }
  },
  computed: {
    remaining() {
      return this.todos.filter(t => !t.done).length
    },
  },
  methods: {
    addTodo() {
      const text = this.newTodo.trim()
      if (!text) return
      this.todos.push({ id: Date.now(), text, done: false })
      this.newTodo = ''
    },
    toggleTodo(id) {
      const todo = this.todos.find(t => t.id === id)
      if (todo) todo.done = !todo.done
    },
    removeTodo(id) {
      this.todos = this.todos.filter(t => t.id !== id)
    },
  },
}
</script>

<style scoped>
.done span {
  text-decoration: line-through;
}
</style>
