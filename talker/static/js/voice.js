class VoiceClient {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.ws = null;
        this.audioContext = null;
        this.workletNode = null;
        this.stream = null;
        this.isListening = false;
        this.isPlaying = false;

        this.micBtn = document.getElementById("mic-btn");
        this.statusEl = document.getElementById("status");
        this.transcriptEl = document.getElementById("transcript");
        this.stateEl = document.getElementById("state-info");
        this.levelEl = document.getElementById("mic-level");
    }

    async connect() {
        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        this.ws = new WebSocket(`${proto}//${location.host}/ws/voice/${this.sessionId}`);

        this.ws.onmessage = (event) => this._handleMessage(JSON.parse(event.data));
        this.ws.onclose = () => this._setStatus("Disconnected");
        this.ws.onerror = () => this._setStatus("Connection error");
        this.ws.onopen = () => this._setStatus("Connected — tap mic to speak");
    }

    async startMic() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this._setStatus("Mic requires HTTPS — check your connection");
            return;
        }
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: { sampleRate: 16000, channelCount: 1 }
            });
        } catch (e) {
            this._setStatus("Mic access denied");
            return;
        }

        this.audioContext = new AudioContext({ sampleRate: 16000 });
        await this.audioContext.audioWorklet.addModule("/static/js/audio-processor.js");

        const source = this.audioContext.createMediaStreamSource(this.stream);
        this.workletNode = new AudioWorkletNode(this.audioContext, "pcm-processor");

        this.workletNode.port.onmessage = (event) => {
            if (this.isListening && this.ws && this.ws.readyState === WebSocket.OPEN) {
                const b64 = this._arrayBufferToBase64(event.data);
                this.ws.send(JSON.stringify({ type: "audio", data: b64 }));
            }
        };

        source.connect(this.workletNode);
        this.workletNode.connect(this.audioContext.destination);

        const analyser = this.audioContext.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        this._animateLevel(analyser);
    }

    toggleListening() {
        if (this.isPlaying) {
            this.ws.send(JSON.stringify({ type: "interrupt" }));
            this.isPlaying = false;
        }

        if (this.isListening) {
            this.isListening = false;
            this.ws.send(JSON.stringify({ type: "stop" }));
            this.micBtn.classList.remove("active");
            this._setStatus("Processing...");
        } else {
            this.isListening = true;
            this.ws.send(JSON.stringify({ type: "start" }));
            this.micBtn.classList.add("active");
            this._setStatus("Listening...");
        }
    }

    _handleMessage(msg) {
        switch (msg.type) {
            case "transcript":
                this._addTranscript("You", msg.text, "user");
                break;
            case "response":
                this._addTranscript("Assistant", msg.text, "assistant");
                if (msg.audio) this._playAudio(msg.audio);
                break;
            case "state":
                this._updateState(msg);
                break;
            case "safety":
                this._addTranscript("Safety Alert", msg.message, "safety");
                if (msg.audio) this._playAudio(msg.audio);
                break;
            case "listening":
                if (msg.active) this._setStatus("Ready — tap to speak");
                break;
            case "error":
                this._setStatus(`Error: ${msg.message}`);
                break;
        }
    }

    _addTranscript(role, text, cls) {
        const div = document.createElement("div");
        div.className = `chat-message chat-${cls}`;
        div.innerHTML = `<div class="chat-role">${role}</div><div class="chat-content">${this._escapeHtml(text)}</div>`;
        this.transcriptEl.appendChild(div);
        this.transcriptEl.scrollTop = this.transcriptEl.scrollHeight;
    }

    _escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    _updateState(msg) {
        if (msg.state === "screening") {
            this.stateEl.innerHTML = `<strong>${this._escapeHtml(msg.instrument)}</strong> — Question ${msg.question} of ${msg.total}`;
        } else if (msg.state === "conversation") {
            this.stateEl.innerHTML = "<strong>Follow-up Conversation</strong>";
        } else if (msg.state === "completed") {
            this.stateEl.innerHTML = "<strong>Assessment Complete</strong>";
            this._setStatus("Done");
            window.location.href = `/assess/summary?session_id=${this.sessionId}`;
        }
    }

    async _playAudio(b64Data) {
        this.isPlaying = true;
        const bytes = Uint8Array.from(atob(b64Data), c => c.charCodeAt(0));
        const int16 = new Int16Array(bytes.buffer);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 32768.0;
        }
        const buffer = this.audioContext.createBuffer(1, float32.length, 16000);
        buffer.getChannelData(0).set(float32);
        const source = this.audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(this.audioContext.destination);
        source.onended = () => { this.isPlaying = false; };
        source.start();
    }

    _animateLevel(analyser) {
        const data = new Uint8Array(analyser.frequencyBinCount);
        const update = () => {
            analyser.getByteFrequencyData(data);
            const avg = data.reduce((a, b) => a + b, 0) / data.length;
            const pct = Math.min(100, (avg / 128) * 100);
            if (this.levelEl) this.levelEl.style.width = `${pct}%`;
            requestAnimationFrame(update);
        };
        update();
    }

    _setStatus(text) {
        if (this.statusEl) this.statusEl.textContent = text;
    }

    _arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = "";
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }
}
