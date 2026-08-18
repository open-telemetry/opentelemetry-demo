// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { checkoutScenario } from './script.js'

export const options = {
    thresholds: {
        http_req_failed: ['rate==0'],
    },
    scenarios: {
        checkout: {
            executor: 'shared-iterations',
            vus: 1,
            iterations: 2,
        },
    },
}

export default checkoutScenario
