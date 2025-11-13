// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

/**
 * Splunk RUM User Attributes Generator
 * This script generates deterministic user attributes based on session ID
 * Ported from the original Go implementation
 */

// Simple hash function for session ID
function simpleHash(str) {
  var hash = 0;
  for (var i = 0; i < str.length; i++) {
    var char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash);
}

// Seeded random number generator
function SeededRandom(seed) {
  this.seed = seed;
}

SeededRandom.prototype.random = function() {
  var a = 1664525;
  var c = 1013904223;
  var m = Math.pow(2, 32);
  this.seed = (a * this.seed + c) % m;
  return this.seed / m;
};

SeededRandom.prototype.randomInt = function(min, max) {
  return Math.floor(this.random() * (max - min + 1)) + min;
};

// Generate user based on session ID
function randomUser(sessionID) {
  var hash = simpleHash(sessionID);
  var rng = new SeededRandom(hash);
  var r = rng.random();

  var user;
  if (r < 0.08) {
    // 8% Admin users
    var adminIDs = [34, 37, 41];
    var adminIndex = rng.randomInt(0, adminIDs.length - 1);
    user = {
      id: adminIDs[adminIndex].toString(),
      role: 'Admin'
    };
  } else if (r < 0.50) {
    // 42% Member users
    user = {
      id: rng.randomInt(1000, 6000).toString(),
      role: 'Member'
    };
  } else {
    // 50% Guest users
    user = {
      id: '99999',
      role: 'Guest'
    };
  }

  console.log('Generated user from session ID:', sessionID, '-> User ID:', user.id, 'Role:', user.role);
  return user;
}

// Generate a UUID v4
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0;
    var v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// Get or create session ID from localStorage with 30-minute expiration
function getSessionId() {
  try {
    var SESSION_TIMEOUT = 30 * 60 * 1000; // 30 minutes in milliseconds
    var now = Date.now();
    var session = localStorage.getItem('session');

    if (session) {
      var sessionObj = JSON.parse(session);
      var sessionAge = now - (sessionObj.timestamp || 0);

      // Check if session is expired (older than 30 minutes)
      if (sessionObj.timestamp && sessionAge < SESSION_TIMEOUT) {
        return sessionObj.userId;
      } else {
        console.log('Session expired or invalid, creating new session');
      }
    }

    // Create new session if it doesn't exist or is expired
    var newUserId = generateUUID();
    var newSession = {
      userId: newUserId,
      currencyCode: 'USD',
      timestamp: now
    };
    localStorage.setItem('session', JSON.stringify(newSession));
    console.log('New session created with 30-minute expiration');
    return newUserId;
  } catch (e) {
    console.error('Error getting/creating session:', e);
    return null;
  }
}

// Main function to generate Splunk RUM global attributes
function getSplunkGlobalAttributes() {
  // Get session ID and generate user attributes
  var sessionId = getSessionId();
  console.log('Session ID for RUM:', sessionId);

  var user = sessionId ? randomUser(sessionId) : { id: '99999', role: 'Guest' };

  var attributes = {
    'enduser.id': user.id,
    'enduser.role': user.role,
    'deployment.type': window.ENV.DEPLOYMENT_TYPE || 'green'
  };

  console.log('Generated Splunk RUM User Attributes:', attributes);
  return attributes;
}
