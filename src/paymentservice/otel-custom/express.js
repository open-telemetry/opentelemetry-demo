import { HttpExtendedAttribute } from './constants';
import { shouldCaptureBodyByMimeType } from './mime-type';
import { StreamChunks } from './stream-chunks';

export const requestHook = (span, req, res) => {
    span.setAttributes({
        [HttpExtendedAttribute.HTTP_PATH]: req.path,
        [HttpExtendedAttribute.HTTP_REQUEST_HEADERS]: JSON.stringify(req.headers),
    });

    const requestMimeType = req.get('content-type');
    const captureRequestBody = shouldCaptureBodyByMimeType(requestMimeType);
    const requestStreamChunks = new StreamChunks();

    if (captureRequestBody) {
        req.on('data', (chunk) => requestStreamChunks.addChunk(chunk));
    }

    const responseStreamChunks = new StreamChunks();

    const originalResWrite = res.write;

    (res).write = function (chunk) {
        responseStreamChunks.addChunk(chunk);
        originalResWrite.apply(res, arguments);
    };
    

    const oldResEnd = res.end;
    res.end = function (chunk) {
        oldResEnd.apply(res, arguments);

        const responseMimeType = res.get('content-type');
        const captureResponseBody = shouldCaptureBodyByMimeType(responseMimeType);
        if (captureResponseBody) responseStreamChunks.addChunk(chunk);

        span.setAttributes({
            [HttpExtendedAttribute.HTTP_REQUEST_BODY]: captureRequestBody
                ? requestStreamChunks.getBody()
                : `Request body not collected due to unsupported mime type: ${requestMimeType}`,
            [HttpExtendedAttribute.HTTP_RESPONSE_BODY]: captureResponseBody
                ? responseStreamChunks.getBody()
                : `Response body not collected due to unsupported mime type: ${responseMimeType}`,
        });


        span.setAttributes({
            [HttpExtendedAttribute.HTTP_RESPONSE_HEADERS]: JSON.stringify(res.getHeaders()),
        });
    };
};

export const expressInstrumentationConfig = {
    requestHook,
};
