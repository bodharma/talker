class PCMProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._buffer = [];
        this._bufferSize = 4096; // ~256ms at 16kHz
    }

    process(inputs) {
        const input = inputs[0];
        if (input.length === 0) return true;

        const channelData = input[0];
        for (let i = 0; i < channelData.length; i++) {
            const s = Math.max(-1, Math.min(1, channelData[i]));
            this._buffer.push(s < 0 ? s * 0x8000 : s * 0x7FFF);
        }

        if (this._buffer.length >= this._bufferSize) {
            const int16 = new Int16Array(this._buffer);
            this.port.postMessage(int16.buffer, [int16.buffer]);
            this._buffer = [];
        }

        return true;
    }
}

registerProcessor("pcm-processor", PCMProcessor);
