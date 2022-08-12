import getSymbolFromCurrency from 'currency-symbol-map';
import SessionGateway from '../../gateways/Session.gateway';

describe('Home Page', () => {
  beforeEach(() => {
    cy.visit(Cypress.env('baseUrl'));
  });

  it('should validate the home page', () => {
    cy.get('[data-cy="home-page"]').should('exist');
    cy.get('[data-cy="product-list"] [data-cy="product-card"]').should('have.length', 9);

    cy.get('[data-cy="session-id"]').should('contain', SessionGateway.getSession().userId);
  });

  it('should change currency', () => {
    cy.get('[data-cy="currency-switcher"]').select('EUR');
    cy.get('[data-cy="product-list"] [data-cy="product-card"]').should('have.length', 9);

    cy.get('[data-cy="currency-switcher"]').should('have.value', 'EUR');

    cy.get('[data-cy="product-card"]').should('contain', getSymbolFromCurrency('EUR'));
  });
});
