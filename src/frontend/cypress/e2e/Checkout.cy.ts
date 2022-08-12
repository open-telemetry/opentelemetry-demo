describe('Checkout Flow', () => {
  beforeEach(() => {
    cy.visit(Cypress.env('baseUrl'));
  });

  it('should create an order with two items', () => {
    cy.get('[data-cy="product-card"]').first().click();
    cy.get('[data-cy="add-to-cart"]').click();

    cy.get('[data-cy="cart-item-count"]').should('contain', '1');

    cy.visit(Cypress.env('baseUrl'));

    cy.get('[data-cy="product-card"]').last().click();
    cy.get('[data-cy="add-to-cart"]').click();

    cy.get('[data-cy="cart-item-count"]').should('contain', '2');

    cy.get('[data-cy="cart-icon"]').click();
    cy.get('[data-cy="cart-go-to-shopping"]').click();

    cy.location('href').should('match', /\/cart$/);

    cy.get('[data-cy="checkout-place-order"]').click();

    cy.wait(5000);
    cy.location('href').should('match', /\/checkout/);
    cy.get('[data-cy="checkout-item"]').should('have.length', 2);
  });
});

export {};
