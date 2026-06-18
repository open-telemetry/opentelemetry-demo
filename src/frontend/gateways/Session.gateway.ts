// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { v4 } from 'uuid';

interface ISession {
  userId: string;
  currencyCode: string;
  userEmail: string;
  userName: string;
}

const sessionKey = 'session';

const getDefaultUserLabel = (userId: string) => `user-${userId.slice(0, 8)}`;

const getUserNameFromEmail = (email: string) => {
  const [localPart = ''] = email.split('@');
  return localPart.trim();
};

const hydrateSession = (session: Partial<ISession>): ISession => {
  const userId = session.userId || v4();
  const userEmail = session.userEmail?.trim() || `${getDefaultUserLabel(userId)}@example.com`;
  const userName = session.userName?.trim() || getUserNameFromEmail(userEmail) || getDefaultUserLabel(userId);

  return {
    userId,
    currencyCode: session.currencyCode || 'USD',
    userEmail,
    userName,
  };
};

const defaultSession: Readonly<ISession> = Object.freeze(hydrateSession({}));

const SessionGateway = () => ({
  getSession(): ISession {
    if (typeof window === 'undefined') return defaultSession;
    const sessionString = localStorage.getItem(sessionKey);

    if (sessionString) {
      try {
        const parsed: unknown = JSON.parse(sessionString);
        if (isValid(parsed)) {
          const hydratedSession = hydrateSession(parsed);

          if (JSON.stringify(hydratedSession) !== sessionString) {
            localStorage.setItem(sessionKey, JSON.stringify(hydratedSession));
          }

          return hydratedSession;
        }
      } catch (e) {
        console.warn('Failed to parse session from localStorage', e);
      }
    }
    localStorage.setItem(sessionKey, JSON.stringify(defaultSession));
    return defaultSession;
  },
  setSessionValue<K extends keyof ISession>(key: K, value: ISession[K]) {
    const session = this.getSession();
    const nextSession = hydrateSession({ ...session, [key]: value });

    localStorage.setItem(sessionKey, JSON.stringify(nextSession));
    return nextSession;
  },
  setUserEmail(userEmail: string) {
    const session = this.getSession();
    const nextSession = hydrateSession({
      ...session,
      userEmail,
      userName: getUserNameFromEmail(userEmail),
    });

    localStorage.setItem(sessionKey, JSON.stringify(nextSession));
    return nextSession;
  },
});

const isValid = (session: unknown): session is ISession => {
  return (
    typeof session === 'object' &&
    session !== null &&
    typeof (session as ISession).userId === 'string' &&
    typeof (session as ISession).currencyCode === 'string' &&
    (typeof (session as ISession).userEmail === 'undefined' || typeof (session as ISession).userEmail === 'string') &&
    (typeof (session as ISession).userName === 'undefined' || typeof (session as ISession).userName === 'string')
  );
};

export default SessionGateway();
