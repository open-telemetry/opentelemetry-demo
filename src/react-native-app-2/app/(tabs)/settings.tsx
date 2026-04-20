// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import { useQueryClient } from '@tanstack/react-query'
import { ThemedView } from "@/components/ThemedView";
import { StyleSheet } from "react-native";
import { getFrontendProxyURL, setFrontendProxyURL } from "@/utils/Settings";
import { setupTracerProvider } from "@/hooks/useTracer";
import { trace } from "@opentelemetry/api";
import { Setting } from "@/components/Setting";

export default function Settings() {
  const queryClient = useQueryClient()

  const onSetFrontendProxyURL = async (value: string) => {
    await setFrontendProxyURL(value);

    // Clear any cached queries since we now have a new endpoint to hit for everything
    await queryClient.invalidateQueries();

    // Need to setup a new tracer provider since the export URL for traces has now changed
    trace.disable();
    const provider = setupTracerProvider(value);
    trace.setGlobalTracerProvider(provider);
  };

  return (
    <ThemedView style={styles.container}>
      <Setting name="Frontend Proxy URL" get={getFrontendProxyURL} set={onSetFrontendProxyURL} />
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    display: "flex",
    gap: 20,
    paddingLeft: 20,
    height: "100%",
  },
});
