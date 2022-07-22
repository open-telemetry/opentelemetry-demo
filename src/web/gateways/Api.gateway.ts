import { Ad, Cart, CartItem, Money, OrderResult, PlaceOrderRequest, Product } from '../protos/demo';
import { IProductCart, IProductCartItem } from '../types/Cart';
import request from '../utils/Request';

const basePath = '/api';

const ApiGateway = () => ({
  getCart() {
    return request<IProductCart>({
      url: `${basePath}/cart`,
    });
  },
  addCartItem(item: CartItem) {
    return request<Cart>({
      url: `${basePath}/cart`,
      body: { item, userId: '123' },
      method: 'POST',
    });
  },
  emptyCart() {
    return request<undefined>({
      url: `${basePath}/cart`,
      method: 'DELETE',
      body: { userId: '123' },
    });
  },

  getSupportedCurrencyList() {
    return request<string[]>({
      url: `${basePath}/currency`,
    });
  },
  convertToCurrency({ from, toCode }: { from: Money; toCode: string }) {
    return request<Money>({
      url: `${basePath}/currency/convert`,
      method: 'POST',
      body: { from, toCode },
    });
  },

  getShippingCost(itemList: IProductCartItem[]) {
    return request<Money>({
      url: `${basePath}/shipping`,
      queryParams: {
        itemList: JSON.stringify(itemList.map(({ productId, quantity }) => ({ productId, quantity }))),
      },
    });
  },

  placeOrder(order: PlaceOrderRequest) {
    return request<OrderResult>({
      url: `${basePath}/checkout`,
      method: 'POST',
      body: order,
    });
  },

  listProducts() {
    return request<Product[]>({
      url: `${basePath}/products`,
    });
  },
  getProduct(productId: string) {
    return request<Product>({
      url: `${basePath}/products/${productId}`,
    });
  },
  listRecommendations(productIds: string[]) {
    return request<Product[]>({
      url: `${basePath}/recommendations`,
      queryParams: {
        productIds,
      },
    });
  },
  listAds(productIds: string[]) {
    return request<Ad[]>({
      url: `${basePath}/data`,
      queryParams: {
        productIds,
      },
    });
  },
});

export default ApiGateway();
