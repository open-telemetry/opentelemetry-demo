

import BugsnagPerformance from '@bugsnag/browser-performance'
const { BUGSNAG_API_KEY = '' } =
    typeof window !== 'undefined' ? window.ENV : {};


const FrontendTracer = async () => {
    BugsnagPerformance.start({
        apiKey: BUGSNAG_API_KEY,
        autoInstrumentNetworkRequests: true,
        networkRequestCallback: (requestInfo) => {
            requestInfo.propagateTraceContext = true;
            return requestInfo;
        }
    });
};

export default FrontendTracer;