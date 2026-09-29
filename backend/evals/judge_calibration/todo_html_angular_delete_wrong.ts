import { Component } from '@angular/core';

interface Todo {
  id: number;
  text: string;
  done: boolean;
}

@Component({
  selector: 'app-todo-list',
  template: `
    <div class="todo-list">
      <h2>My Todos</h2>
      <input [(ngModel)]="newTodo" placeholder="What needs doing?" />
      <button (click)="addTodo()">Add</button>
      <p *ngIf="todos.length === 0">No todos yet</p>
      <ul *ngIf="todos.length > 0">
        <li *ngFor="let todo of todos" [class.done]="todo.done">
          <input type="checkbox" [checked]="todo.done" (change)="toggleTodo(todo.id)" />
          <span>{{ todo.text }}</span>
          <button (click)="removeTodo(todo.id)">Delete</button>
        </li>
      </ul>
      <p>{{ remaining }} remaining</p>
    </div>
  `,
  styles: [`.done span { text-decoration: line-through; }`],
})
export class TodoListComponent {
  todos: Todo[] = [];
  newTodo = '';

  get remaining(): number {
    return this.todos.filter(t => !t.done).length;
  }

  addTodo(): void {
    const text = this.newTodo.trim();
    if (!text) return;
    this.todos = [...this.todos, { id: Date.now(), text, done: false }];
    this.newTodo = '';
  }

  toggleTodo(id: number): void {
    this.todos = this.todos.map(t => (t.id === id ? { ...t, done: !t.done } : t));
  }

  removeTodo(id: number): void {
    this.todos = this.todos.filter(t => t.id === id);
  }
}
