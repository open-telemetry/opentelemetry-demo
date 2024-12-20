// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Copied with modification from src/frontend/providers/Cart.provider.tsx
 */
import React, { createContext, useCallback, useContext, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ApiGateway from "@/gateways/Api.gateway";
import { CartItem, OrderResult, PlaceOrderRequest } from "@/protos/demo";
import { IProductCart } from "@/types/Cart";

interface IContext {
  cart: IProductCart;
  addItem(item: CartItem): void;
  emptyCart(): void;
  placeOrder(order: PlaceOrderRequest): Promise<OrderResult>;
}

export const Context = createContext<IContext>({
  cart: { userId: "", items: [] },
  addItem: () => {},
  emptyCart: () => {},
  placeOrder: () => Promise.resolve({} as OrderResult),
});

interface IProps {
  children: React.ReactNode;
}

export const useCart = () => useContext(Context);

const CartProvider = ({ children }: IProps) => {
  // TODO simplify react native demo for now by hard-coding the selected currency
  const selectedCurrency = "USD";
  const queryClient = useQueryClient();
  const mutationOptions = useMemo(
    () => ({
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["cart"] });
      },
    }),
    [queryClient],
  );

  const { data: cart = { userId: "", items: [] } } = useQuery(
    ["cart", selectedCurrency],
    () => ApiGateway.getCart(selectedCurrency),
  );
  const addCartMutation = useMutation(ApiGateway.addCartItem, mutationOptions);
  const emptyCartMutation = useMutation(ApiGateway.emptyCart, mutationOptions);
  const placeOrderMutation = useMutation(
    ApiGateway.placeOrder,
    mutationOptions,
  );

  const addItem = useCallback(
    (item: CartItem) =>
      addCartMutation.mutateAsync({ ...item, currencyCode: selectedCurrency }),
    [addCartMutation, selectedCurrency],
  );
  const emptyCart = useCallback(
    () => emptyCartMutation.mutateAsync(),
    [emptyCartMutation],
  );
  const placeOrder = useCallback(
    (order: PlaceOrderRequest) =>
      placeOrderMutation.mutateAsync({
        ...order,
        currencyCode: selectedCurrency,
      }),
    [placeOrderMutation, selectedCurrency],
  );

  const value = useMemo(
    () => ({ cart, addItem, emptyCart, placeOrder }),
    [cart, addItem, emptyCart, placeOrder],
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
};

export default CartProvider;
