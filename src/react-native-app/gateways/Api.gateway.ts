// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Copied with modification from src/frontend/gateways/Api.gateway.ts
 *
 * TODO The React Native example only implements a subset of the functionality defined here, missing in particular is:
 *  - showing ads
 *  - showing recommendations
 *  - calculating shipping costs
 *  - currency conversion
 */
import {
  Ad,
  Address,
  Cart,
  CartItem,
  Money,
  PlaceOrderRequest,
  Product,
} from "@/protos/demo";
import { IProductCart, IProductCartItem, IProductCheckout } from "@/types/Cart";
import request from "@/utils/Request";
import SessionGateway from "./Session.gateway";
import { context, propagation } from "@opentelemetry/api";

const basePath = "/api";

const Apis = () => ({
  async getCart(currencyCode: string) {
    const { userId } = await SessionGateway.getSession();
    return request<IProductCart>({
      url: `${basePath}/cart`,
      queryParams: { sessionId: userId, currencyCode },
    });
  },
  async addCartItem({
    currencyCode,
    ...item
  }: CartItem & { currencyCode: string }) {
    const { userId } = await SessionGateway.getSession();
    return request<Cart>({
      url: `${basePath}/cart`,
      body: { item, userId },
      queryParams: { currencyCode },
      method: "POST",
    });
  },
  async emptyCart() {
    const { userId } = await SessionGateway.getSession();
    return request<undefined>({
      url: `${basePath}/cart`,
      method: "DELETE",
      body: { userId },
    });
  },

  getSupportedCurrencyList() {
    return request<string[]>({
      url: `${basePath}/currency`,
    });
  },

  getShippingCost(
    itemList: IProductCartItem[],
    currencyCode: string,
    address: Address,
  ) {
    return request<Money>({
      url: `${basePath}/shipping`,
      queryParams: {
        itemList: JSON.stringify(
          itemList.map(({ productId, quantity }) => ({ productId, quantity })),
        ),
        currencyCode,
        address: JSON.stringify(address),
      },
    });
  },

  placeOrder({
    currencyCode,
    ...order
  }: PlaceOrderRequest & { currencyCode: string }) {
    return request<IProductCheckout>({
      url: `${basePath}/checkout`,
      method: "POST",
      queryParams: { currencyCode },
      body: order,
    });
  },

  listProducts(currencyCode: string) {
    return request<Product[]>({
      url: `${basePath}/products`,
      queryParams: { currencyCode },
    });
  },
  getProduct(productId: string, currencyCode: string) {
    return request<Product>({
      url: `${basePath}/products/${productId}`,
      queryParams: { currencyCode },
    });
  },
  async listRecommendations(productIds: string[], currencyCode: string) {
    const { userId } = await SessionGateway.getSession();
    return request<Product[]>({
      url: `${basePath}/recommendations`,
      queryParams: {
        productIds,
        sessionId: userId,
        currencyCode,
      },
    });
  },
  listAds(contextKeys: string[]) {
    return request<Ad[]>({
      url: `${basePath}/data`,
      queryParams: {
        contextKeys,
      },
    });
  },
});

/**
 * Extends all the API calls to set baggage automatically.
 */
const ApiGateway = new Proxy(Apis(), {
  get(target, prop, receiver) {
    const originalFunction = Reflect.get(target, prop, receiver);

    if (typeof originalFunction !== "function") {
      return originalFunction;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return async function (...args: any[]) {
      const { userId } = await SessionGateway.getSession();
      const baggage =
        propagation.getActiveBaggage() || propagation.createBaggage();
      const newBaggage = baggage.setEntry("session.id", { value: userId });
      const newContext = propagation.setBaggage(context.active(), newBaggage);
      return context.with(newContext, () => {
        return Reflect.apply(originalFunction, undefined, args);
      });
    };
  },
});

export default ApiGateway;
