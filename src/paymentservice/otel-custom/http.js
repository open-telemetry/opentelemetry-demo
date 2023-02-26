const { IncomingMessage, ClientRequest } = require('http');
const { HttpExtendedAttribute } = require('./constants');
const { shouldCaptureBodyByMimeType } = require('./mime-type');
const { StreamChunks } = require('./stream-chunks');

const streamChunksKey = Symbol('opentelemetry.instrumentation.http.StreamChunks');

const httpCustomAttributes = (
    span,
    request,
    response
) => {
    if (request instanceof ClientRequest) {
        const reqPath = request.path.split('?')[0];
        span.setAttribute(HttpExtendedAttribute.HTTP_PATH, reqPath);
        span.setAttribute(
            HttpExtendedAttribute.HTTP_REQUEST_HEADERS,
            JSON.stringify((request).getHeaders())
        );
    }
    if (response instanceof IncomingMessage) {
        span.setAttribute(
            HttpExtendedAttribute.HTTP_RESPONSE_HEADERS,
            JSON.stringify((response).headers)
        );
    }

    const requestBody = request[streamChunksKey];
    if (requestBody) {
        span.setAttribute(HttpExtendedAttribute.HTTP_REQUEST_BODY, requestBody.getBody());
    }

    const responseBody = response[streamChunksKey];
    if (responseBody) {
        span.setAttribute(HttpExtendedAttribute.HTTP_RESPONSE_BODY, responseBody.getBody());
    }
};

const httpCustomAttributesOnRequest = (span, request) => {
    if (request instanceof ClientRequest) {
        const requestMimeType = request.getHeader('content-type');
        if (!shouldCaptureBodyByMimeType(requestMimeType)) {
            span.setAttribute(
                HttpExtendedAttribute.HTTP_REQUEST_BODY,
                `Request body not collected due to unsupported mime type: ${requestMimeType}`
            );
            return;
        }

        let oldWrite = request.write;
        request[streamChunksKey] = new StreamChunks();
        request.write = function (data) {
            const expectDevData = request[streamChunksKey];
            expectDevData?.addChunk(data);
            return oldWrite.call(request, data);
        };
    }
};

const httpCustomAttributesOnResponse = (span, response) => {
    if (response instanceof IncomingMessage) {
        const responseMimeType = response.headers?.['content-type'];
        if (!shouldCaptureBodyByMimeType(responseMimeType)) {
            span.setAttribute(
                HttpExtendedAttribute.HTTP_RESPONSE_BODY,
                `Response body not collected due to unsupported mime type: ${responseMimeType}`
            );
            return;
        }

        response[streamChunksKey] = new StreamChunks();
        const origPush = response.push;
        response.push = function (chunk) {
            if (chunk) {
                const expectDevData = response[streamChunksKey];
                expectDevData?.addChunk(chunk);
            }
            return origPush.apply(this, arguments);
        };
    }
};

const httpInstrumentationConfig = {
    applyCustomAttributesOnSpan: httpCustomAttributes,
    requestHook: httpCustomAttributesOnRequest,
    responseHook: httpCustomAttributesOnResponse,
    headersToSpanAttributes: {
        client: {
            requestHeaders: ['traceloop_id'],
            responseHeaders: ['traceloop_id'],
        },
        server: {
            requestHeaders: ['traceloop_id'],
            responseHeaders: ['traceloop_id'],
        },
    },
};

module.exports = {
    httpInstrumentationConfig
};
