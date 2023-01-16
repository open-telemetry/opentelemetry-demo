import {Address, Cart, OrderItem, OrderResult, Product} from '../protos/demo';

export interface IProductCartItem {
  productId: string;
  quantity: number;
  product: Product;
}

export interface IProductCheckoutItem extends OrderItem {
  item: IProductCartItem;
}

export interface IProductCheckout extends OrderResult {
  items: IProductCheckoutItem[];
  shippingAddress: Address;
}

export interface IProductCart extends Cart {
  items: IProductCartItem[];
}
