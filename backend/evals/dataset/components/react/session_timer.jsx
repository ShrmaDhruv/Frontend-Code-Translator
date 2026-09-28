import { useState, useEffect } from 'react'

export default function SessionTimer({ label = 'Session', limit = 60 }) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setSeconds(s => s + 1), 1000)
    return () => clearInterval(id)
  }, [])

  const minutesPart = String(Math.floor(seconds / 60)).padStart(2, '0')
  const secondsPart = String(seconds % 60).padStart(2, '0')
  const formatted = `${minutesPart}:${secondsPart}`
  const expired = seconds >= limit

  const reset = () => setSeconds(0)

  return (
    <div className="session-timer">
      <h2>{label}</h2>
      <p className="time">{formatted}</p>
      {expired && <p className="warning">Time's up!</p>}
      <button onClick={reset}>Reset</button>
    </div>
  )
}
