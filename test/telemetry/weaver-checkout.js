// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { checkoutScenario } from './script.js'

export const options = {
    scenarios: {
        checkout: {
            executor: 'shared-iterations',
            vus: 1,
            iterations: 2,
        },
    },
}

export default checkoutScenario
