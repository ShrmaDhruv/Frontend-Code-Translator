import { useState } from 'react'

export default function Counter({ initial = 0, step = 1 }) {
  const [count, setCount] = useState(initial)
  const isEven = count % 2 === 0

  const increment = () => setCount(c => c + step)
  const decrement = () => setCount(c => c - step)
  const reset = () => setCount(initial)

  return (
    <div className="counter">
      <h2>Count: {count}</h2>
      <p>{isEven ? 'Even' : 'Odd'}</p>
      <button onClick={decrement}>-</button>
      <button onClick={increment}>+</button>
      <button onClick={reset}>Reset</button>
    </div>
  )
}
