// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import { SplashScreen, Stack } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  DarkTheme,
  DefaultTheme,
  ThemeProvider,
} from "@react-navigation/native";
import { useColorScheme } from "react-native";
import { RootSiblingParent } from "react-native-root-siblings";
import Toast from "react-native-toast-message";
import { useFonts } from "expo-font";
import { useEffect, useMemo } from "react";
import { useTracer } from "@/hooks/useTracer";
import CartProvider from "@/providers/Cart.provider";

const queryClient = new QueryClient();

export default function RootLayout() {
  const colorScheme = useColorScheme();
  const [fontsLoaded] = useFonts({
    SpaceMono: require("../assets/fonts/SpaceMono-Regular.ttf"),
  });
  const { loaded: tracerLoaded } = useTracer();

  const loaded = useMemo<boolean>(
    () => fontsLoaded && tracerLoaded,
    [fontsLoaded, tracerLoaded],
  );
  useEffect(() => {
    if (loaded) {
      SplashScreen.hideAsync();
    }
  }, [loaded]);

  if (!loaded) {
    return null;
  }

  return (
    <ThemeProvider value={colorScheme === "dark" ? DarkTheme : DefaultTheme}>
      <RootSiblingParent>
        <QueryClientProvider client={queryClient}>
          <CartProvider>
            {/*
              TODO Once https://github.com/open-telemetry/opentelemetry-js-contrib/pull/2359 is available it can
              be used here to provide telemetry for navigation between tabs
              */}
            <Stack>
              <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            </Stack>
          </CartProvider>
        </QueryClientProvider>
      </RootSiblingParent>
      <Toast />
    </ThemeProvider>
  );
}
