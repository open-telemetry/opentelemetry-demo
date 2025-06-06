// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { Address, CartItem, GetQuoteResponse } from '../../protos/demo';

const { SHIPPING_ADDR = '' } = process.env;

// Transform address from camelCase to snake_case for HTTP API
const transformAddress = (address: Address) => ({
  street_address: address.streetAddress,
  city: address.city,
  state: address.state,
  country: address.country,
  zip_code: address.zipCode,
});

// Transform cart items from camelCase to snake_case for HTTP API
const transformCartItems = (items: CartItem[]) => 
  items.map(item => ({
    product_id: item.productId,
    quantity: item.quantity,
  }));

const ShippingGateway = () => ({
  async getShippingCost(itemList: CartItem[], address: Address): Promise<GetQuoteResponse> {
    const requestBody = {
      items: transformCartItems(itemList),
      address: transformAddress(address),
    };

    const response = await fetch(`${SHIPPING_ADDR}/get-quote`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP error: ${response.status} ${response.statusText} - ${errorText}`);
    }

    const data = await response.json();
    
    const costUsd = data.cost_usd ? {
      currencyCode: data.cost_usd.currency_code,
      units: data.cost_usd.units,
      nanos: data.cost_usd.nanos,
    } : undefined;

    const transformedResponse: GetQuoteResponse = {
      costUsd,
    };
    
    return transformedResponse;
  },
});

export default ShippingGateway(); 
