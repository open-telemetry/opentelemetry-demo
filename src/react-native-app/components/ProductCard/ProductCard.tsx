// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Copied with modification from src/frontend/components/ProductCard/ProductCard.tsx
 */
import { Product } from "@/protos/demo";
import { ThemedView } from "@/components/ThemedView";
import { useState, useEffect, useMemo } from "react";
import getLocalhost from "@/utils/Localhost";
import { Image, Pressable, StyleSheet } from "react-native";
import { ThemedText } from "@/components/ThemedText";
import { useThemeColor } from "@/hooks/useThemeColor";

interface IProps {
  product: Product;
  onClickAdd: () => void;
}

async function getImageURL(picture: string) {
  const localhost = await getLocalhost();
  return `http://${localhost}:${process.env.EXPO_PUBLIC_FRONTEND_PROXY_PORT}/images/products/${picture}`;
}

const ProductCard = ({
  product: {
    picture,
    name,
    priceUsd = {
      currencyCode: "USD",
      units: 0,
      nanos: 0,
    },
  },
  onClickAdd,
}: IProps) => {
  const tint = useThemeColor({}, "tint");
  const styles = useMemo(() => getStyles(tint), [tint]);
  const [imageSrc, setImageSrc] = useState<string>("");

  useEffect(() => {
    getImageURL(picture)
      .then(setImageSrc)
      .catch((reason) => {
        console.warn("Failed to get image URL: ", reason);
      });
  }, [picture]);

  // TODO simplify react native demo for now by hard-coding the selected currency
  const price = (priceUsd?.units + priceUsd?.nanos / 100000000).toFixed(2);

  return (
    <ThemedView style={styles.container}>
      <ThemedView>
        {imageSrc && <Image style={styles.image} source={{ uri: imageSrc }} />}
      </ThemedView>
      <ThemedView style={styles.productInfo}>
        <ThemedText style={styles.name}>{name}</ThemedText>
        <ThemedText style={styles.price}>$ {price}</ThemedText>
        <Pressable style={styles.add} onPress={onClickAdd}>
          <ThemedText style={styles.addText}>Add to Cart</ThemedText>
        </Pressable>
      </ThemedView>
    </ThemedView>
  );
};

const getStyles = (tint: string) =>
  StyleSheet.create({
    container: {
      display: "flex",
      flexDirection: "row",
      padding: 20,
      marginLeft: 10,
      marginRight: 10,
      borderStyle: "solid",
      borderBottomWidth: 1,
      borderColor: tint,
      gap: 30,
    },
    image: {
      width: 100,
      height: 100,
    },
    productInfo: {
      flexShrink: 1,
    },
    name: {},
    price: {
      fontWeight: "bold",
    },
    add: {
      borderRadius: 4,
      backgroundColor: "green",
      alignItems: "center",
      width: 100,
    },
    addText: {
      color: "white",
    },
  });

export default ProductCard;
