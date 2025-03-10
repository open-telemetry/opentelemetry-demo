// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// This file is meant to be implemented by forks of the OpenTelemetry Demo repository
// to showcase custom observability functionality implemented by the fork.
// The OpenTelemetry Demo repository will not modify this file, allowing forks to
// demonstrate their own unique functionality without merge conflicts.

class chargeHooks {
  constructor(request) {
    this.request = request;
  }

  // The preHook function is called before the charge span is started
  preHook() {

  }

  // The startHook function is called after the charge span is started
  startHook() {

  }

  // The endHook function is called before the charge span is ended
  endHook() {

  }

  // The postHook function is called after the charge span is ended
  postHook() {

  }
}

module.exports = chargeHooks;
