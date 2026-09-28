import { useState, useMemo } from 'react'

export default function TodoList({ title = 'My Todos' }) {
  const [todos, setTodos] = useState([])
  const [newTodo, setNewTodo] = useState('')
  const remaining = useMemo(() => todos.filter(t => !t.done).length, [todos])

  const addTodo = () => {
    const text = newTodo.trim()
    if (!text) return
    setTodos([...todos, { id: Date.now(), text, done: false }])
    setNewTodo('')
  }

  const toggleTodo = (id) => {
    setTodos(todos.map(t => (t.id === id ? { ...t, done: !t.done } : t)))
  }

  const removeTodo = (id) => {
    setTodos(todos.filter(t => t.id !== id))
  }

  return (
    <div className="todo-list">
      <h2>{title}</h2>
      <input
        value={newTodo}
        onChange={e => setNewTodo(e.target.value)}
        placeholder="What needs doing?"
      />
      <button onClick={addTodo}>Add</button>
      {todos.length === 0 ? (
        <p>No todos yet</p>
      ) : (
        <ul>
          {todos.map(todo => (
            <li key={todo.id} className={todo.done ? 'done' : ''}>
              <input
                type="checkbox"
                checked={todo.done}
                onChange={() => toggleTodo(todo.id)}
              />
              <span>{todo.text}</span>
              <button onClick={() => removeTodo(todo.id)}>Delete</button>
            </li>
          ))}
        </ul>
      )}
      <p>{remaining} remaining</p>
    </div>
  )
}
