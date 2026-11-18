// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { getElementByField } from '../../utils/Cypress';
import { CypressFields } from '../../utils/enums/CypressFields';

const FLAGD_READ_URL = '/feature/api/read';
const FLAGD_WRITE_URL = '/feature/api/write';

const setWebInteractionSlowdown = (defaultVariant: string) => {
  cy.request('GET', FLAGD_READ_URL).then(({ body }) => {
    body.flags.webInteractionSlowdown.defaultVariant = defaultVariant;

    cy.request('POST', FLAGD_WRITE_URL, { data: body });
  });
};

describe('Web interaction slowdown', () => {
  before(() => setWebInteractionSlowdown('600k'));
  after(() => setWebInteractionSlowdown('off'));

  it('should still reach the cart when Add To Cart is clicked', () => {
    cy.visit('/');
    getElementByField(CypressFields.ProductCard).first().click();
    getElementByField(CypressFields.ProductAddToCart).click();

    cy.location('href', { timeout: 15000 }).should('match', /\/cart$/);
  });
});

export {};
