// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const FLAGD_READ_URL = '/feature/api/read';
const FLAGD_WRITE_URL = '/feature/api/write';

const setPaymentFailure = (defaultVariant: string) => {
  cy.request('GET', FLAGD_READ_URL).then(({ body }) => {
    body.flags.paymentFailure.defaultVariant = defaultVariant;

    cy.request('POST', FLAGD_WRITE_URL, { data: body });
  });
};

describe('Checkout API payment failure handling', () => {
  before(() => setPaymentFailure('100%'));
  after(() => setPaymentFailure('off'));

  it('returns a structured JSON error instead of an unhandled 500', () => {
    const userId = `cypress-payment-failure-${Date.now()}`;

    cy.request('POST', '/api/cart', {
      userId,
      item: { productId: '0PUK6V6EV0', quantity: 1 },
    });

    cy.request({
      method: 'POST',
      url: '/api/checkout?currencyCode=USD',
      failOnStatusCode: false,
      body: {
        userId,
        userCurrency: 'USD',
        address: {
          streetAddress: '1600 Amphitheatre Parkway',
          city: 'Mountain View',
          state: 'CA',
          country: 'USA',
          zipCode: '94043',
        },
        email: 'cypress-test@example.com',
        creditCard: {
          creditCardNumber: '4432801561520454',
          creditCardCvv: 123,
          creditCardExpirationYear: new Date().getFullYear() + 1,
          creditCardExpirationMonth: 1,
        },
      },
    }).then(response => {
      expect(response.status).to.eq(500);
      expect(response.body).to.have.property('error').that.is.a('string').and.is.not.empty;
    });
  });
});

export {};
