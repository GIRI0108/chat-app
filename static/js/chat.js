const socket = io({ transports: ["websocket"] });
let conv_id = null;

socket.on("connect", () => {
    socket.emit("start_conversation", { other_id: OTHER_ID });
});

socket.on("conversation", data => {
    conv_id = data.conv_id;
    socket.emit("join_conv", { conv_id });
});

socket.on("history", msgs => msgs.forEach(renderMessage));
socket.on("new_message", renderMessage);

function renderMessage(m) {
    const div = document.getElementById("messages");
    const box = document.createElement("div");

    box.className = (m.sender_id === CURRENT_USER_ID) ? "me" : "other";
    box.innerHTML = `
    <small>${new Date(m.timestamp).toLocaleString()}</small>
    <div>${m.content || ""}</div>
  `;

    div.appendChild(box);
    div.scrollTop = div.scrollHeight;
}

document.getElementById("send").onclick = async () => {
    const msgInput = document.getElementById("msg");
    const fileInput = document.getElementById("file");

    const msg = msgInput.value;
    const file = fileInput.files[0];

    if (!msg && !file) return;

    if (file) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("conv_id", conv_id);

        const res = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        if (data.success) {
  let fileUrl = data.url;

  // ✅ PDF force download
  if (file.type === "application/pdf") {
    fileUrl = data.url + "?dl=1";
  }

  const fileMessage =
    '<a href="' + fileUrl + '" target="_blank" download>' +
    '📎 ' + file.name +
    '</a>';

  socket.emit("send_message", {
    conv_id: conv_id,
    content: fileMessage
  });
}



        fileInput.value = "";
    }

    if (msg) {
        socket.emit("send_message", { conv_id, content: msg });
        msgInput.value = "";
    }
};

document.getElementById("privateRoomBtn").onclick = () => {
    window.location.href = "/private-room";
};
