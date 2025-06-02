"use client";

import {sdk} from '@embrace-io/web-sdk';

const EmbraceFrontendTracer = () => {

    console.log('hello here we go');

    sdk.initSDK({
    appID: 'p9feh',
    });
}

export default EmbraceFrontendTracer;

