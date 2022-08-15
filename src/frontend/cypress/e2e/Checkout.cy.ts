import { CypressFields, getElementByField } from '../../utils/Cypress';

describe('Checkout Flow', () => {
  beforeEach(() => {
    cy.visit('/');
  });

  it('should create an order with two items', () => {
    getElementByField(CypressFields.ProductCard).first().click();
    getElementByField(CypressFields.ProductAddToCart).click();

    getElementByField(CypressFields.CartItemCount).should('contain', '1');

    cy.visit('/');

    getElementByField(CypressFields.ProductCard).last().click();
    getElementByField(CypressFields.ProductAddToCart).click();

    getElementByField(CypressFields.CartItemCount).should('contain', '2');

    getElementByField(CypressFields.CartIcon).click();
    getElementByField(CypressFields.CartGoToShopping).click();

    cy.location('href').should('match', /\/cart$/);

    getElementByField(CypressFields.CheckoutPlaceOrder).click();

    cy.wait(5000);
    cy.location('href').should('match', /\/checkout/);
    getElementByField(CypressFields.CheckoutItem).should('have.length', 2);
  });
});

export {};
