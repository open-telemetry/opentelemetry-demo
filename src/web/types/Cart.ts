import { Cart, Product } from '../protos/demo';

export interface IProductCartItem {
  productId: string;
  quantity: number;
  product: Product;
}

export interface IProductCart extends Cart {
  items: IProductCartItem[];
}
