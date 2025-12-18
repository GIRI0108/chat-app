function createRoom() {
  let code = document.getElementById("createCode").value;

  if (code.length !== 6) {
    alert("Enter 6 digit code");
    return;
  }

  window.location.href = `/vibe/${code}?role=host`;
}

function joinRoom() {
  let code = document.getElementById("joinCode").value;

  if (code.length !== 6) {
    alert("Enter valid code");
    return;
  }

  window.location.href = `/vibe/${code}?role=user`;
}
