let mediaRecorder;
let audioChunks = [];

function startRecordingLive() {
  const listeningBox = document.getElementById("listening-box");

  listeningBox.innerText = "🎙 Listening...";
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

      try {
        const res = await fetch("/transcribe", {
          method: "POST",
          body: formData
        });

        const data = await res.json();
        const transcript = data.transcription;
        console.log("Transcription:", transcript);

      // Pre-fill input box (but don't send it yet)
        document.getElementById("user-input").value = transcript;
        sendMessage();

      } catch (err) {
        console.error("Transcription failed:", err);
        listeningBox.innerText = "⚠️ Transcription failed.";
      }

      listeningBox.innerText = "";
    };
  })
    .catch(err => {
      console.error("Microphone access denied or failed:", err);
      listeningBox.innerText = "🎙 Microphone not available.";
    });
}

function stopRecordingLive() {
  const listeningBox = document.getElementById("listening-box");
  listeningBox.innerText = "";
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  listeningBox.innerText = "";
}

async function sendMessage() {
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const dateInput = document.getElementById("date-start");


  const message = input.value.trim();
  if (!message) return;

  chatBox.innerHTML += `<p><b>You:</b> ${message}</p>`;
  const date = dateInput?.value;
  input.value = "";


  body = { ...{ message } };
  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });

  const data = await response.json();
  console.log("AI Response:", data);
  chatBox.innerHTML += `<p><b>AI:</b> ${data.response}</p>`;
}

function summarizeEntries() {
  const chatBox = document.getElementById("chat-box");
  const dateStart = document.getElementById("date-start");
  const dateEnd = document.getElementById("date-end");


  chatBox.innerHTML += `<p><b>Summarizing entries from </b> ${dateStart.value} <b>to</b> ${dateEnd.value}</p>`;
  const voiceOn = document.getElementById("voice-output").checked;

  body = { date_start: dateStart.value, date_end: dateEnd.value, voice_on: voiceOn};
  fetch("/summarize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
  .then(res => res.json())
  .then(data => {
    if (voiceOn) {
      const byteChars = atob(data.audio_data);
      const byteNumbers = new Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) {
        byteNumbers[i] = byteChars.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: data.mime_type });
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      audio.play();
    }
    chatBox.innerHTML += `<p><b>Summary:</b> ${data.summary}</p>`;
  });
}