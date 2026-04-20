// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import {Pressable, StyleSheet, TextInput, type TextInputProps} from "react-native";
import { ThemedView } from "@/components/ThemedView";
import { ThemedText } from "@/components/ThemedText";
import { useThemeColor } from "@/hooks/useThemeColor";
import {useCallback, useEffect, useState} from "react";
import Toast from "react-native-toast-message";

export type SettingProps = TextInputProps & {
  name: string;
  get: () => Promise<string>;
  set: (value: string) => Promise<void>;
};

export function Setting({ name, get, set, ...otherProps }: SettingProps) {
  const color = useThemeColor({}, "text");
  const [loading, setLoading] = useState(false);
  const [text, setText] = useState('');

  useEffect(() => {
    get().then(existingValue => {
      setText(existingValue);
      setLoading(false);
    });
  }, []);

  const onApply = useCallback(async () => {
    await set(text);

    Toast.show({
      type: "success",
      position: "bottom",
      text1: `${name} applied`,
    });
  }, [text]);

  return (
    <ThemedView style={styles.container}>
      <ThemedText>{name}:</ThemedText>
      {loading ? (
        <ThemedText>Fetching current value...</ThemedText>
      ) : (
        <>
          <TextInput
            style={{ color }}
            onChangeText={setText}
            value={text}
             {...otherProps}
          />
          <Pressable style={styles.apply} onPress={onApply}>
            <ThemedText style={styles.applyText}>Apply</ThemedText>
          </Pressable>
        </>
      )}
    </ThemedView>
  );
}


const styles = StyleSheet.create({
  container: {
    display: "flex",
    gap: 5,
  },
  apply: {
    borderRadius: 4,
    backgroundColor: "green",
    alignItems: "center",
    width: 100,
    position: "relative",
  },
  applyText: {
    color: "white",
  },
});
