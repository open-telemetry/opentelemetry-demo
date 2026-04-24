// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { v4 } from 'uuid';

interface ISession {
  userId: string;
  currencyCode: string;
}

const sessionKey = 'session';
const defaultSession = {
  userId: v4(),
  currencyCode: 'USD',
};

const SessionGateway = () => ({
  getSession(): ISession {
    if (typeof window === 'undefined') return defaultSession;
    const sessionString = localStorage.getItem(sessionKey);

    let session: ISession | null = null;
    if (sessionString) {
      try {
        session = JSON.parse(sessionString);
      } catch {
        session = null;
      }
    }
    if (!session || !isValid(session)) {
      session = { ...defaultSession };
      localStorage.setItem(sessionKey, JSON.stringify(session));
    }
    return session;
  },
  setSessionValue<K extends keyof ISession>(key: K, value: ISession[K]) {
    const session = this.getSession();

    localStorage.setItem(sessionKey, JSON.stringify({ ...session, [key]: value }));
  },
});

const isValid = (session: any): boolean => {
  return (
    typeof session === 'object' &&
    session !== null &&
    typeof (session as ISession).userId === 'string' &&
    typeof (session as ISession).currencyCode === 'string'
  );
};

export default SessionGateway();
