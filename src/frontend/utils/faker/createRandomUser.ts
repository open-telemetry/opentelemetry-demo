// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { faker } from '@faker-js/faker';
import { persistedCall } from './persistedCall';

export const createRandomUser = persistedCall('random_user', () => {
  const firstName = faker.person.firstName();
  const lastName = faker.person.lastName();

  return {
    userId: faker.string.uuid(),
    username: faker.internet.username(), // before version 9.1.0, use userName()
    fullName: `${firstName} ${lastName}`,
    email: faker.internet.email({ firstName: firstName.toLowerCase(), lastName: lastName.toLowerCase() }),
    userAgent: faker.internet.userAgent(),
  };
});
