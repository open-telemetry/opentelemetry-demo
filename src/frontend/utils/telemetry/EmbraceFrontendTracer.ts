"use client";

import {sdk} from '@embrace-io/web-sdk';

const EmbraceFrontendTracer = () => {

    sdk.initSDK({
    appID: 'p9feh',
    appVersion: '0.1.0',
    });
}

export default EmbraceFrontendTracer;

