const socket = io({ transports: ["websocket"] });
const audio = document.getElementById("audio");

socket.emit("join_room", { room: ROOM });

function loadAudio() {
  const file = document.getElementById("audioFile").files[0];
  const url = document.getElementById("audioUrl").value;

  if (file) {
    const blobUrl = URL.createObjectURL(file);
    audio.src = blobUrl;
    socket.emit("audio_load", { room: ROOM, src: blobUrl });
  } else if (url) {
    audio.src = url;
    socket.emit("audio_load", { room: ROOM, src: url });
  }
}

audio.onplay = () =>
  socket.emit("audio_play", { room: ROOM, time: audio.currentTime });

audio.onpause = () =>
  socket.emit("audio_pause", { room: ROOM, time: audio.currentTime });

audio.onseeked = () =>
  socket.emit("audio_seek", { room: ROOM, time: audio.currentTime });

socket.on("audio_load", d => audio.src = d.src);
socket.on("audio_play", d => {
  audio.currentTime = d.time;
  audio.play();
});
socket.on("audio_pause", d => {
  audio.currentTime = d.time;
  audio.pause();
});
socket.on("audio_seek", d => audio.currentTime = d.time);
