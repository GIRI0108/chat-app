const socket = io();

let localVideo;
let remoteVideo;
let startBtn;

let localStream;
let pc;

const params = new URLSearchParams(window.location.search);
const room = params.get("room");

const iceConfig = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
};

/* 🔥 WAIT FOR DOM */
window.onload = () => {
  localVideo = document.getElementById("localVideo");
  remoteVideo = document.getElementById("remoteVideo");
  startBtn = document.getElementById("startCallBtn");

  startBtn.onclick = startCall;
};

async function startCall() {
  startBtn.remove();

  try {
    localStream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: true
    });

    localVideo.srcObject = localStream;

    pc = new RTCPeerConnection(iceConfig);

    localStream.getTracks().forEach(track => {
      pc.addTrack(track, localStream);
    });

    pc.ontrack = e => {
      remoteVideo.srcObject = e.streams[0];
    };

    pc.onicecandidate = e => {
      if (e.candidate) {
        socket.emit("call:ice", { room, candidate: e.candidate });
      }
    };

    socket.emit("call:join", { room });

  } catch (err) {
    alert("❌ Camera / Mic access denied");
    console.error(err);
  }
}

/* 🔔 SOCKET EVENTS */

socket.on("call:start", async () => {
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  socket.emit("call:offer", { room, offer });
});

socket.on("call:offer", async data => {
  await pc.setRemoteDescription(new RTCSessionDescription(data.offer));
  const answer = await pc.createAnswer();
  await pc.setLocalDescription(answer);
  socket.emit("call:answer", { room, answer });
});

socket.on("call:answer", async data => {
  await pc.setRemoteDescription(new RTCSessionDescription(data.answer));
});

socket.on("call:ice", async data => {
  if (data.candidate) {
    await pc.addIceCandidate(new RTCIceCandidate(data.candidate));
  }
});

function endCall() {
  if (pc) pc.close();
  if (localStream) {
    localStream.getTracks().forEach(t => t.stop());
  }
  socket.disconnect();
  window.close();
}
