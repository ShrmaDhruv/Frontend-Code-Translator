import { Component, Input } from '@angular/core'

interface Todo {
  id: number
  text: string
  done: boolean
}

@Component({
  selector: 'app-todo-list',
  template: `
    <div class="todo-list">
      <h2>{{ title }}</h2>
      <input [(ngModel)]="newTodo" placeholder="What needs doing?" />
      <button (click)="addTodo()">Add</button>
      <p *ngIf="todos.length === 0; else list">No todos yet</p>
      <ng-template #list>
        <ul>
          <li *ngFor="let todo of todos" [class.done]="todo.done">
            <input type="checkbox" [checked]="todo.done" (change)="toggleTodo(todo.id)" />
            <span>{{ todo.text }}</span>
            <button (click)="removeTodo(todo.id)">Delete</button>
          </li>
        </ul>
      </ng-template>
      <p>{{ remaining }} remaining</p>
    </div>
  `,
  styles: [`.done span { text-decoration: line-through; }`],
})
export class TodoListComponent {
  @Input() title: string = 'My Todos'
  todos: Todo[] = []
  newTodo: string = ''

  get remaining(): number {
    return this.todos.filter(t => !t.done).length
  }

  addTodo(): void {
    const text = this.newTodo.trim()
    if (!text) return
    this.todos = [...this.todos, { id: Date.now(), text, done: false }]
    this.newTodo = ''
  }

  toggleTodo(id: number): void {
    this.todos = this.todos.map(t => (t.id === id ? { ...t, done: !t.done } : t))
  }

  removeTodo(id: number): void {
    this.todos = this.todos.filter(t => t.id !== id)
  }
}
