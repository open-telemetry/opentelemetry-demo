// for body with at most this length, full body will be captured.
// for large body with more than this amount of bytes, we will
// collect at least this amount of bytes, but might truncate after it
const MIN_COLLECTED_BODY_LENGTH = 524288;

class StreamChunks {
    chunks;
    length;

    constructor() {
        this.chunks = [];
        this.length = 0;
    }

    addChunk(chunk) {
        if (this.length >= MIN_COLLECTED_BODY_LENGTH) return;

        const chunkLength = chunk?.length;
        if (!chunkLength) return;

        this.chunks.push(chunk);
        this.length += chunkLength;
    }

    getBody() {
        return this.chunks.join('');
    }
}

module.exports = {
    StreamChunks,
    MIN_COLLECTED_BODY_LENGTH,
};
