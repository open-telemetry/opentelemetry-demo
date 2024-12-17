// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import { ScrollView, type ScrollViewProps } from "react-native";
import { useThemeColor } from "@/hooks/useThemeColor";

export type ThemedViewProps = ScrollViewProps & {
  lightColor?: string;
  darkColor?: string;
};

export function ThemedScrollView({
  style,
  lightColor,
  darkColor,
  ...otherProps
}: ThemedViewProps) {
  const backgroundColor = useThemeColor(
    { light: lightColor, dark: darkColor },
    "background",
  );

  return <ScrollView style={[{ backgroundColor }, style]} {...otherProps} />;
}
