// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Copied with modification from src/frontend/components/Cart/CartDetail.tsx
 */
import { router } from "expo-router";
import { ThemedView } from "@/components/ThemedView";
import { ThemedText } from "@/components/ThemedText";
import { Pressable, StyleSheet } from "react-native";
import { useCart } from "@/providers/Cart.provider";
import CheckoutForm from "@/components/CheckoutForm";
import EmptyCart from "@/components/EmptyCart";
import { ThemedScrollView } from "@/components/ThemedScrollView";
import { useCallback, useMemo } from "react";
import { IFormData } from "@/components/CheckoutForm/CheckoutForm";
import Toast from "react-native-toast-message";
import SessionGateway from "@/gateways/Session.gateway";
import { useThemeColor } from "@/hooks/useThemeColor";

export default function Cart() {
  const tint = useThemeColor({}, "tint");
  const styles = useMemo(() => getStyles(tint), [tint]);
  const {
    cart: { items },
    emptyCart,
    placeOrder,
  } = useCart();

  const onEmptyCart = useCallback(() => {
    emptyCart();
    Toast.show({
      type: "success",
      position: "bottom",
      text1: "Your cart was emptied",
    });
  }, [emptyCart]);

  const onPlaceOrder = useCallback(
    async ({
      email,
      state,
      streetAddress,
      country,
      city,
      zipCode,
      creditCardCvv,
      creditCardExpirationMonth,
      creditCardExpirationYear,
      creditCardNumber,
    }: IFormData) => {
      const { userId } = await SessionGateway.getSession();
      await placeOrder({
        userId,
        email,
        address: {
          streetAddress,
          state,
          country,
          city,
          zipCode,
        },
        // TODO simplify react native demo for now by hard-coding the selected currency
        userCurrency: "USD",
        creditCard: {
          creditCardCvv,
          creditCardExpirationMonth,
          creditCardExpirationYear,
          creditCardNumber,
        },
      });

      Toast.show({
        type: "success",
        position: "bottom",
        text1: "Your order is Complete!",
        text2: "We've sent you a confirmation email.",
      });

      router.replace("/");
    },
    [placeOrder],
  );

  if (!items.length) {
    return <EmptyCart />;
  }

  return (
    <ThemedView style={styles.container}>
      <ThemedView>
        <ThemedScrollView>
          {items.map((item) => (
            <ThemedView key={item.productId} style={styles.cartItem}>
              <ThemedText>{item.product.name}</ThemedText>
              <ThemedText style={styles.bold}>{item.quantity}</ThemedText>
            </ThemedView>
          ))}
        </ThemedScrollView>
      </ThemedView>
      <ThemedView style={styles.emptyCartContainer}>
        <Pressable style={styles.emptyCart} onPress={onEmptyCart}>
          <ThemedText style={styles.emptyCartText}>Empty Cart</ThemedText>
        </Pressable>
      </ThemedView>
      <CheckoutForm onSubmit={onPlaceOrder} />
    </ThemedView>
  );
}

const getStyles = (tint: string) =>
  StyleSheet.create({
    container: {
      flex: 1,
      gap: 20,
      justifyContent: "flex-start",
    },
    emptyCartContainer: {
      display: "flex",
      alignItems: "flex-end",
    },
    emptyCart: {
      borderRadius: 4,
      backgroundColor: "green",
      alignItems: "center",
      width: 100,
      right: 20,
      position: "relative",
    },
    emptyCartText: {
      color: "white",
    },
    cartItem: {
      marginLeft: 20,
      marginRight: 20,
      display: "flex",
      flexDirection: "row",
      justifyContent: "space-between",
      borderStyle: "solid",
      borderBottomWidth: 1,
      borderColor: tint,
    },
    bold: {
      fontWeight: "bold",
    },
  });
