

import BugsnagPerformance from '@bugsnag/browser-performance'

const { BUGSNAG_API_KEY = '' } =
    typeof window !== 'undefined' ? window.ENV : {};

const FrontendTracer = async () => {
    BugsnagPerformance.start({
        apiKey: BUGSNAG_API_KEY,

    });
};

export default FrontendTracer;