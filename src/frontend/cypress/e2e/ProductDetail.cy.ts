import { CypressFields, getElementByField } from '../../utils/Cypress';

describe('Product Detail Page', () => {
  beforeEach(() => {
    cy.visit('/');
  });

  it('should validate the product detail page', () => {
    getElementByField(CypressFields.ProductCard).first().click();

    getElementByField(CypressFields.ProductDetail).should('exist');
    getElementByField(CypressFields.ProductPicture).should('exist');
    getElementByField(CypressFields.ProductName).should('exist');
    getElementByField(CypressFields.ProductDescription).should('exist');
    getElementByField(CypressFields.ProductAddToCart).should('exist');

    getElementByField(CypressFields.ProductCard, getElementByField(CypressFields.RecommendationList)).should(
      'have.length',
      4
    );
    getElementByField(CypressFields.Ad).should('exist');
  });

  it('should add item to cart', () => {
    getElementByField(CypressFields.ProductCard).first().click();
    getElementByField(CypressFields.ProductAddToCart).click();

    getElementByField(CypressFields.CartItemCount).should('contain', '1');
    getElementByField(CypressFields.CartIcon).click();

    getElementByField(CypressFields.CartDropdownItem).should('have.length', 1);
  });
});

export {};
