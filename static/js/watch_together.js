const socket = io({ transports: ["websocket"] });
const video = document.getElementById("video");

socket.emit("join_room", { room: ROOM });

function loadVideo() {
  const file = document.getElementById("videoFile").files[0];
  const url = document.getElementById("videoUrl").value;

  if (file) {
    const blobUrl = URL.createObjectURL(file);
    video.src = blobUrl;
    socket.emit("video_load", { room: ROOM, src: blobUrl });
  } else if (url) {
    video.src = url;
    socket.emit("video_load", { room: ROOM, src: url });
  }
}

video.onplay = () =>
  socket.emit("video_play", { room: ROOM, time: video.currentTime });

video.onpause = () =>
  socket.emit("video_pause", { room: ROOM, time: video.currentTime });

video.onseeked = () =>
  socket.emit("video_seek", { room: ROOM, time: video.currentTime });

socket.on("video_load", d => video.src = d.src);
socket.on("video_play", d => {
  video.currentTime = d.time;
  video.play();
});
socket.on("video_pause", d => {
  video.currentTime = d.time;
  video.pause();
});
socket.on("video_seek", d => video.currentTime = d.time);
