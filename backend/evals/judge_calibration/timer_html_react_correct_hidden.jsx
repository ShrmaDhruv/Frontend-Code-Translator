import { useState, useEffect } from 'react'

function formatTime(total) {
  const m = String(Math.floor(total / 60)).padStart(2, '0')
  const s = String(total % 60).padStart(2, '0')
  return m + ':' + s
}

export default function SessionTimer({ label = 'Session', limit = 60 }) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const intervalId = setInterval(() => setSeconds(s => s + 1), 1000)
    return () => clearInterval(intervalId)
  }, [])

  const reset = () => setSeconds(0)

  return (
    <div className="session-timer">
      <h2>{label}</h2>
      <p className="time">{formatTime(seconds)}</p>
      <p className="warning" hidden={seconds < limit}>Time's up!</p>
      <button onClick={reset}>Reset</button>
    </div>
  )
}
