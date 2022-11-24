// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { faro } from '@grafana/faro-web-sdk';
import { Ad, Address, Cart, CartItem, Money, PlaceOrderRequest, Product } from '../protos/demo';
import { IProductCart, IProductCartItem, IProductCheckout } from '../types/Cart';
import request from '../utils/Request';
import SessionGateway from './Session.gateway';

const { userId } = SessionGateway.getSession();

const basePath = '/api';

const ApiGateway = () => ({
  getCart(currencyCode: string) {
    return request<IProductCart>({
      url: `${basePath}/cart`,
      queryParams: { sessionId: userId, currencyCode },
    }).catch((error) => {
      faro.api?.pushError(error);
      return Promise.reject(error);
    });
  },
  addCartItem({ currencyCode, ...item }: CartItem & { currencyCode: string }) {
    return request<Cart>({
      url: `${basePath}/cart`,
      body: { item, userId },
      queryParams: { currencyCode },
      method: 'POST',
    }).catch((error) => {
      faro.api?.pushError(error);
      return Promise.reject(error);
    });
  },
  emptyCart() {
    return request<undefined>({
      url: `${basePath}/cart`,
      method: 'DELETE',
      body: { userId },
    }).catch((error) => {
      faro.api?.pushError(error);
      return Promise.reject(error);
    });
  },

  getSupportedCurrencyList() {
    return request<string[]>({
      url: `${basePath}/currency`,
    }).catch((error) => {
      faro.api?.pushError(error);
      return Promise.reject(error);
    });
  },

  getShippingCost(itemList: IProductCartItem[], currencyCode: string, address: Address) {
    return request<Money>({
      url: `${basePath}/shipping`,
      queryParams: {
        itemList: JSON.stringify(itemList.map(({ productId, quantity }) => ({ productId, quantity }))),
        currencyCode,
        address: JSON.stringify(address),
      },
    }).catch((error) => {
      faro.api?.pushError(error);
      return Promise.reject(error);
    });
  },

  placeOrder({ currencyCode, ...order }: PlaceOrderRequest & { currencyCode: string }) {
    return request<IProductCheckout>({
      url: `${basePath}/checkout`,
      method: 'POST',
      queryParams: { currencyCode },
      body: order,
    }).catch((error) => {
      faro.api?.pushError(error);
      return Promise.reject(error);
    });
  },

  listProducts(currencyCode: string) {
    return request<Product[]>({
      url: `${basePath}/products`,
      queryParams: { currencyCode },
    }).catch((error) => {
      faro.api?.pushError(error);
      return Promise.reject(error);
    });
  },
  getProduct(productId: string, currencyCode: string) {
    return request<Product>({
      url: `${basePath}/products/${productId}`,
      queryParams: { currencyCode },
    }).catch((error) => {
      faro.api?.pushError(error);
      return Promise.reject(error);
    });
  },
  listRecommendations(productIds: string[], currencyCode: string) {
    return request<Product[]>({
      url: `${basePath}/recommendations`,
      queryParams: {
        productIds,
        sessionId: userId,
        currencyCode
      },
    }).catch((error) => {
      faro.api?.pushError(error);
      return Promise.reject(error);
    });
  },
  listAds(contextKeys: string[]) {
    return request<Ad[]>({
      url: `${basePath}/data`,
      queryParams: {
        contextKeys,
      },
    }).catch((error) => {
      faro.api?.pushError(error);
      return Promise.reject(error);
    });
  },
});

export default ApiGateway();
