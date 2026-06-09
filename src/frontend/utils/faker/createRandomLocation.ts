// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { faker } from '@faker-js/faker';
import { persistedCall } from './persistedCall';

type LocationSeed = {
    countryCode: string;
    continentCode: string;
    locality: string;
    lat?: number;
    lon?: number;
}

export const createRandomLocation = persistedCall('random_location', (seed?: LocationSeed) => {
  const continent = faker.location.continent();
  // @ts-expect-error we simply don't care.
  const continentCode = continentCodes[continent] ?? 'EU';
  const country = faker.location.countryCode();
  const locality = faker.location.city();

  // Jitter ~10km around the seeded city; random global point when unseeded.
  const [lat, lon] = seed?.lat != null && seed?.lon != null
    ? faker.location.nearbyGPSCoordinate({ origin: [seed.lat, seed.lon], radius: 10, isMetric: true })
    : faker.location.nearbyGPSCoordinate();

  return {
    'geo.continent.code': seed?.continentCode || continentCode,
    'geo.country.iso_code': seed?.countryCode || country,
    'geo.locality.name': seed?.locality || locality,
    'geo.location.lat': lat,
    'geo.location.lon': lon,
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
