document.addEventListener("DOMContentLoaded", () => {
    const recordButton = document.getElementById("recordButton");
    const statusDiv = document.getElementById("status");
    let websocket;
    let mediaRecorder;
    let audioContext;
    let audioQueue = [];
    let isPlaying = false;
    let isRecording = false;

    const SERVER_URI = "ws://localhost:8000/ws/talk";

    recordButton.addEventListener("click", () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    function connectWebSocket() {
        websocket = new WebSocket(SERVER_URI);

        websocket.onopen = () => {
            statusDiv.textContent = "Connected. Ready to record.";
            console.log("WebSocket connection established.");
        };

        websocket.onmessage = (event) => {
            if (typeof event.data === 'string') {
                console.log("Server message:", event.data);
                if (event.data === "TTS_COMPLETE") {
                    playNextInQueue(); // Start playing the buffered audio
                } else {
                    statusDiv.textContent = event.data;
                }
            } else {
                // Assume binary data is audio, add it to the queue
                audioQueue.push(event.data);
            }
        };

        websocket.onerror = (error) => {
            console.error("WebSocket error:", error);
            statusDiv.textContent = "Connection error. Please refresh.";
        };

        websocket.onclose = () => {
            console.log("WebSocket connection closed.");
            if (isRecording) {
                stopRecording();
            }
        };
    }

    async function startRecording() {
        if (!websocket || websocket.readyState !== WebSocket.OPEN) {
            connectWebSocket();
            // Wait for connection to be established
            await new Promise(resolve => setTimeout(() => {
                if (websocket.readyState === WebSocket.OPEN) resolve();
            }, 1000));
        }

        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(stream => {
                    isRecording = true;
                    recordButton.textContent = "Stop Recording";
                    statusDiv.textContent = "Recording...";
                    
                    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
                    mediaRecorder.ondataavailable = (event) => {
                        if (event.data.size > 0 && websocket.readyState === WebSocket.OPEN) {
                            websocket.send(event.data);
                        }
                    };
                    mediaRecorder.start(250); // Send data every 250ms
                })
                .catch(error => {
                    console.error("Error accessing microphone:", error);
                    statusDiv.textContent = "Could not access microphone.";
                });
        } else {
            statusDiv.textContent = "Your browser does not support audio recording.";
        }
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state === "recording") {
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
            isRecording = false;
            recordButton.textContent = "Start Recording";
            statusDiv.textContent = "Processing...";
            if (websocket.readyState === WebSocket.OPEN) {
                // Send a zero-byte blob to signal the end of the stream.
                websocket.send(new Blob([]));
            }
        }
    }

    async function playNextInQueue() {
        if (audioQueue.length > 0) {
            isPlaying = true;
            const audioBlob = new Blob(audioQueue, { type: 'audio/mpeg' });
            audioQueue = []; // Clear the queue

            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            audio.onended = () => {
                isPlaying = false;
                statusDiv.textContent = "Click 'Start Recording' to begin.";
                URL.revokeObjectURL(audioUrl); // Clean up the object URL
            };
            audio.play();
        } else {
            isPlaying = false;
        }
    }

    // By not calling connectWebSocket() here, we wait for the user to click the button.
    // connectWebSocket();
}); 