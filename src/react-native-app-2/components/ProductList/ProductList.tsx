// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Copied with modification from:
 *  src/frontend/pages/product/[productId]/index.tsx
 *  src/frontend/components/ProductList/ProductList.tsx
 */
import Toast from "react-native-toast-message";
import { useCallback } from "react";
import ProductCard from "@/components/ProductCard";
import { Product } from "@/protos/demo";
import { ThemedScrollView } from "@/components/ThemedScrollView";
import { useCart } from "@/providers/Cart.provider";

interface IProps {
  productList: Product[];
}

const ProductList = ({ productList }: IProps) => {
  const { addItem } = useCart();
  const onAddItem = useCallback(
    async (id: string) => {
      addItem({
        productId: id,
        quantity: 1,
      });

      Toast.show({
        type: "success",
        position: "bottom",
        text1: "This item has been added to your cart",
      });
    },
    [addItem],
  );

  return (
    <ThemedScrollView>
      {productList.map((product) => (
        <ProductCard
          key={product.id}
          product={product}
          onClickAdd={() => onAddItem(product.id)}
        />
      ))}
    </ThemedScrollView>
  );
};

export default ProductList;
