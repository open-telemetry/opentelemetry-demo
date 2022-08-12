describe('Product Detail Page', () => {
  beforeEach(() => {
    cy.visit(Cypress.env('baseUrl'));
  });

  it('should validate the product detail page', () => {
    cy.get('[data-cy="product-card"]').first().click();

    cy.get('[data-cy="product-detail"]').should('exist');
    cy.get('[data-cy="product-picture"]').should('exist');
    cy.get('[data-cy="product-name"]').should('exist');
    cy.get('[data-cy="product-description"]').should('exist');
    cy.get('[data-cy="add-to-cart"]').should('exist');

    cy.get('[data-cy="recommendation-list"] [data-cy="product-card"]').should('have.length', 4);
    cy.get('[data-cy="ad"]').should('exist');
  });

  it('should add item to cart', () => {
    cy.get('[data-cy="product-card"]').first().click();
    cy.get('[data-cy="add-to-cart"]').click();

    cy.get('[data-cy="cart-item-count"]').should('contain', '1');
    cy.get('[data-cy="cart-icon"]').click();

    cy.get('[data-cy="cart-dropdown-item"]').should('have.length', 1);
  });
});

export {};
