// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import { StyleSheet, TextInput, type TextInputProps } from "react-native";
import { ThemedView } from "@/components/ThemedView";
import { ThemedText } from "@/components/ThemedText";
import { useThemeColor } from "@/hooks/useThemeColor";

export type FieldProps = TextInputProps & {
  label: string;
};

export function Field({ label, ...otherProps }: FieldProps) {
  const color = useThemeColor({}, "text");

  return (
    <ThemedView style={styles.container}>
      <ThemedText>{label}:</ThemedText>
      <TextInput style={{ color }} {...otherProps} />
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    display: "flex",
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
  },
});
