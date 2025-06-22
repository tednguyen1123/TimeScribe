let mediaRecorder;
let audioChunks = [];

function startRecordingLive() {
  const listeningBox = document.getElementById("listening-box");

  listeningBox.innerText = "Listening...";
  audioChunks = [];

  navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.start();

    mediaRecorder.ondataavailable = (e) => {
      audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      const fullBlob = new Blob(audioChunks, { type: "audio/webm" });

      const formData = new FormData();
      formData.append("audio", fullBlob, "recording.webm");

      const res = await fetch("/transcribe", {
        method: "POST",
        body: formData
      });

      const data = await res.json();
      const transcript = data.transcription;
      console.log("Transcription:", data);

      // Pre-fill input box (but don't send it yet)
      document.getElementById("user-input").value = transcript;
      sendMessage();
    };
  });
}

function stopRecordingLive() {
  const listeningBox = document.getElementById("listening-box");
  listeningBox.innerText = "";
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
}

async function sendMessage() {
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");

  const message = input.value;
  if (!message) return;

  chatBox.innerHTML += `<p><b>You:</b> ${message}</p>`;
  input.value = "";


  body = { ...{ message } };
  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });

  const data = await response.json();
  chatBox.innerHTML += `<p><b>AI:</b> ${data.response}</p>`;
}
