import { Component, Input, OnInit } from '@angular/core'

@Component({
  selector: 'app-counter',
  template: `
    <div class="counter">
      <h2>Count: {{ count }}</h2>
      <p>{{ isEven ? 'Even' : 'Odd' }}</p>
      <button (click)="decrement()">-</button>
      <button (click)="increment()">+</button>
      <button (click)="reset()">Reset</button>
    </div>
  `,
})
export class CounterComponent implements OnInit {
  @Input() initial: number = 0
  @Input() step: number = 1
  count: number = 0

  get isEven(): boolean {
    return this.count % 2 === 0
  }

  ngOnInit(): void {
    this.count = this.initial
  }

  increment(): void {
    this.count += this.step
  }

  decrement(): void {
    this.count -= this.step
  }

  reset(): void {
    this.count = this.initial
  }
}
