// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import { ThemedView } from "@/components/ThemedView";
import ProductList from "@/components/ProductList";
import { useQuery } from "@tanstack/react-query";
import { ScrollView, StyleSheet } from "react-native";
import { ThemedText } from "@/components/ThemedText";
import ApiGateway from "@/gateways/Api.gateway";

export default function Index() {
  const { data: productList = [] } = useQuery({
    // TODO simplify react native demo for now by hard-coding the selected currency
    queryKey: ["products", "USD"],
    queryFn: () => ApiGateway.listProducts("USD"),
  });

  return (
    <ThemedView style={styles.container}>
      <ScrollView>
        {productList.length ? (
          <ProductList productList={productList} />
        ) : (
          <ThemedText>
            No products found, make sure the backend services for the
            OpenTelemetry demo are running
          </ThemedText>
        )}
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
});
