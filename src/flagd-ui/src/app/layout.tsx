// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import { Layout } from "@/components/Layout";
import "./globals.css";

export const metadata = {
  title: "Flagd Configurator",
  description:
    "Built to provide an easier way to configure the Flagd configurations",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Layout>{children}</Layout>
      </body>
    </html>
  );
}
