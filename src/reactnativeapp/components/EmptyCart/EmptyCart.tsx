// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Copied with modification from src/frontend/components/Cart/EmptyCart.tsx
 */
import { ThemedView } from "@/components/ThemedView";
import { ThemedText } from "@/components/ThemedText";
import { StyleSheet } from "react-native";

const EmptyCart = () => {
  return (
    <ThemedView style={styles.container}>
      <ThemedText style={styles.header}>
        Your shopping cart is empty!
      </ThemedText>
      <ThemedText style={styles.subHeader}>
        Items you add to your shopping cart will appear here.
      </ThemedText>
    </ThemedView>
  );
};

export default EmptyCart;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  header: {
    fontSize: 20,
  },
  subHeader: {
    fontSize: 14,
  },
});
