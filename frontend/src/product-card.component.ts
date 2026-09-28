import { Component } from '@angular/core';

@Component({
  selector: 'app-product-card',
  template: `
    <section class="product-card">
      <p class="eyebrow">New collection</p>
      <h2>Orbit Desk Lamp</h2>
      <p>Warm dimming, brushed metal, and a compact base.</p>
      <button (click)="saved = !saved">
        {{ saved ? 'Saved' : 'Save item' }}
      </button>
    </section>
  `,
})
export class ProductCard {
  saved = false;
}
