import { useState } from 'react'

export default function Counter({ initial = 0, step = 1 }) {
  const [count, setCount] = useState(initial)

  const increment = () => setCount(count + step)
  const decrement = () => setCount(count - step)
  const reset = () => setCount(initial)

  return (
    <div className="counter">
      <h2>Count: {count}</h2>
      <p>{count % 2 ? 'Odd' : 'Even'}</p>
      <button onClick={decrement}>-</button>
      <button onClick={increment}>+</button>
      <button onClick={reset}>Reset</button>
    </div>
  )
}
