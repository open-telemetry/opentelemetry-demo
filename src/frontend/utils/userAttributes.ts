// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

/**
 * User attributes generation based on session ID
 * Port of the Go implementation from the original frontend
 */

export interface User {
  id: number;
  role: string;
}

/**
 * Simple hash function implementation
 * Creates a deterministic hash from a string (similar to Java's hashCode)
 */
function simpleHash(str: string): number {
  let hash = 0;

  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }

  return Math.abs(hash);
}

/**
 * Seeded random number generator
 * Creates a deterministic random number generator from a seed
 */
class SeededRandom {
  private seed: number;

  constructor(seed: number) {
    this.seed = seed;
  }

  /**
   * Returns a pseudo-random number between 0 and 1
   */
  random(): number {
    // Linear congruential generator (LCG)
    const a = 1664525;
    const c = 1013904223;
    const m = Math.pow(2, 32);

    this.seed = (a * this.seed + c) % m;
    return this.seed / m;
  }

  /**
   * Returns a random integer between min and max (inclusive)
   */
  randomInt(min: number, max: number): number {
    return Math.floor(this.random() * (max - min + 1)) + min;
  }
}

/**
 * Generates a deterministic user based on the session ID
 * Matches the Go implementation's distribution:
 * - 8% chance of Admin (IDs: 34, 37, 41)
 * - 42% chance of Member (IDs: 1000-6000)
 * - 50% chance of Guest (ID: 99999)
 */
export function randomUser(sessionID: string): User {
  // Create a deterministic seed from the sessionID
  const hash = simpleHash(sessionID);
  const rng = new SeededRandom(hash);

  const r = rng.random();

  if (r < 0.08) {
    // 8% Admin users
    const adminIDs = [34, 37, 41];
    const adminIndex = rng.randomInt(0, adminIDs.length - 1);
    return {
      id: adminIDs[adminIndex],
      role: 'Admin'
    };
  } else if (r < 0.50) {
    // 42% Member users (0.08 to 0.50)
    return {
      id: rng.randomInt(1000, 6000),
      role: 'Member'
    };
  } else {
    // 50% Guest users
    return {
      id: 99999,
      role: 'Guest'
    };
  }
}

/**
 * Gets Splunk RUM global attributes based on session ID
 * This function should be called to generate user-specific attributes
 */
export function getSplunkUserAttributes(sessionID: string): Record<string, string | number> {
  const user = randomUser(sessionID);

  return {
    'enduser.id': user.id.toString(),
    'enduser.role': user.role,
  };
}
