import { useState } from 'react'

export default function TodoList({ title = 'My Todos' }) {
  const [todos, setTodos] = useState([])
  const [newTodo, setNewTodo] = useState('')

  const remaining = todos.filter(t => !t.done).length

  function addTodo() {
    const text = newTodo.trim()
    if (!text) return
    setTodos([...todos, { id: Date.now(), text, done: false }])
    setNewTodo('')
  }

  function toggleTodo(id) {
    setTodos(todos.map(t => (t.id === id ? { ...t, done: !t.done } : t)))
  }

  function removeTodo(id) {
    setTodos(todos.filter(t => t.id !== id))
  }

  return (
    <div className="todo-list">
      <h2>{title}</h2>
      <input value={newTodo} onChange={e => setNewTodo(e.target.value)} placeholder="What needs doing?" />
      <button onClick={addTodo}>Add</button>
      {!todos.length ? (
        <p>No todos yet</p>
      ) : (
        <ul>
          {todos.map(todo => (
            <li key={todo.id} className={todo.done ? 'done' : ''}>
              <input type="checkbox" checked={todo.done} onChange={() => toggleTodo(todo.id)} />
              <span style={{ textDecoration: todo.done ? 'line-through' : 'none' }}>{todo.text}</span>
              <button onClick={() => removeTodo(todo.id)}>Delete</button>
            </li>
          ))}
        </ul>
      )}
      <p>{remaining} remaining</p>
    </div>
  )
}
