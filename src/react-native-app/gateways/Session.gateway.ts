// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Copied with modification from src/frontend/gateways/Session.gateway.ts
 */
import "react-native-get-random-values"; // Must be imported before 'uuid', see https://stackoverflow.com/a/68097811
import { v4 } from "uuid";
import AsyncStorage from "@react-native-async-storage/async-storage";

interface ISession {
  userId: string;
  currencyCode: string;
}

const sessionKey = "session";
const defaultSession = {
  userId: v4(),
  currencyCode: "USD",
};

const SessionGateway = () => ({
  async getSession(): Promise<ISession> {
    const sessionString = await AsyncStorage.getItem(sessionKey);

    if (!sessionString) {
      await AsyncStorage.setItem(sessionKey, JSON.stringify(defaultSession));
    }

    return JSON.parse(
      sessionString || JSON.stringify(defaultSession),
    ) as ISession;
  },
  setSessionValue<K extends keyof ISession>(key: K, value: ISession[K]) {
    const session = this.getSession();

    return AsyncStorage.setItem(
      sessionKey,
      JSON.stringify({ ...session, [key]: value }),
    );
  },
});

export default SessionGateway();
