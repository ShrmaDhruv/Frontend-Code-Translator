import { Component, Input, OnDestroy, OnInit } from '@angular/core'

@Component({
  selector: 'app-session-timer',
  template: `
    <div class="session-timer">
      <h2>{{ label }}</h2>
      <p class="time">{{ formatted }}</p>
      <p *ngIf="expired" class="warning">Time's up!</p>
      <button (click)="reset()">Reset</button>
    </div>
  `,
})
export class SessionTimerComponent implements OnInit, OnDestroy {
  @Input() label: string = 'Session'
  @Input() limit: number = 60
  seconds: number = 0
  private intervalId?: ReturnType<typeof setInterval>

  get formatted(): string {
    const m = String(Math.floor(this.seconds / 60)).padStart(2, '0')
    const s = String(this.seconds % 60).padStart(2, '0')
    return `${m}:${s}`
  }

  get expired(): boolean {
    return this.seconds >= this.limit
  }

  ngOnInit(): void {
    this.intervalId = setInterval(() => {
      this.seconds++
    }, 1000)
  }

  ngOnDestroy(): void {
    clearInterval(this.intervalId)
  }

  reset(): void {
    this.seconds = 0
  }
}
