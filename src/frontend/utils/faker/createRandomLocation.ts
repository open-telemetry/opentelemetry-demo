// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { faker } from '@faker-js/faker';
import { persistedCall } from './persistedCall';

export const createRandomLocation = persistedCall('random_location', () => {
  const continent = faker.location.continent();
  // @ts-expect-error we simply don't care.
  const continentCode = continentCodes[continent] ?? 'EU';
  const country = faker.location.countryCode();
  const locality = faker.location.city();

  return {
    'geo.continent.code': continentCode,
    'geo.country.iso_code': country,
    'geo.locality.name': locality,
  };
});

const continentCodes = {
  Africa: 'AF',
  Antarctica: 'AN',
  Asia: 'AS',
  Europe: 'EU',
  'North America': 'NA',
  Oceania: 'OC',
  'South America': 'SA',
};
