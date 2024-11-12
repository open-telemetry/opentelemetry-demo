// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import { Tabs } from "expo-router";
import React from "react";
import { TabBarIcon } from "@/components/navigation/TabBarIcon";
import { useCart } from "@/providers/Cart.provider";

export default function TabLayout() {
  const {
    cart: { items },
  } = useCart();

  let itemsInCart = 0;
  items.forEach((item) => {
    itemsInCart += item.quantity;
  });

  return (
    <Tabs>
      <Tabs.Screen
        name="index"
        options={{
          title: "Products",
          tabBarShowLabel: false,
          tabBarIcon: ({ color, focused }) => (
            <TabBarIcon
              name={focused ? "list" : "list-outline"}
              color={color}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="cart"
        options={{
          title: "Cart",
          tabBarShowLabel: false,
          tabBarBadge: itemsInCart || undefined,
          tabBarIcon: ({ color, focused }) => (
            <TabBarIcon
              name={focused ? "cart" : "cart-outline"}
              color={color}
            />
          ),
        }}
      />
    </Tabs>
  );
}
