const allowedMimeTypePrefix = [
    'text',
    'multipart/form-data',
    'application/json',
    'application/ld+json',
    'application/rtf',
    'application/x-www-form-urlencoded',
    'application/xml',
    'application/xhtml',
];

const shouldCaptureBodyByMimeType = (mimeType) => {
    try {
        return !mimeType || allowedMimeTypePrefix.some((prefix) => mimeType.startsWith(prefix));
    } catch {
        return true;
    }
};

module.exports = {
    shouldCaptureBodyByMimeType,
};
