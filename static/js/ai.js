// ai.js — modal + draggable floating button (FINAL FIXED)

document.addEventListener("DOMContentLoaded", () => {
  const aiModal = document.getElementById("aiModal");
  const aiSubmit = document.getElementById("aiSubmit");
  const aiInput = document.getElementById("aiInput");
  const aiTask = document.getElementById("aiTask");
  const langInput = document.getElementById("langInput");
  const aiResult = document.getElementById("aiResult");
  const aiButton = document.getElementById("aiFloatingBtn");
  const aiClose = document.getElementById("aiClose");

  if (!aiModal || !aiButton) {
    console.warn("AI elements not found — skipping AI init");
    return;
  }

  /* =========================
     MODAL OPEN / CLOSE
  ========================== */
  const openModal = () => {
    aiModal.style.display = "flex";
  };

  const closeModal = () => {
    aiModal.style.display = "none";
  };

  aiButton.addEventListener("click", () => {
    if (!isDragging) openModal();
  });

  if (aiClose) {
    aiClose.addEventListener("click", closeModal);
  }

  window.addEventListener("click", (e) => {
    if (e.target === aiModal) closeModal();
  });

  /* =========================
     AI SUBMIT
  ========================== */
  if (aiSubmit) {
    aiSubmit.addEventListener("click", async () => {
      const text = aiInput.value.trim();
      const task = aiTask.value;
      const lang = langInput.value.trim();

      if (!text) {
        aiResult.textContent = "Please enter some text.";
        return;
      }

      aiResult.textContent = "Processing...";

      try {
        const res = await fetch("/api/ai/process", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, task, lang })
        });

        const data = await res.json();
        aiResult.textContent = data.result || "No response from AI.";
      } catch (err) {
        aiResult.textContent = "Error: " + err.message;
      }
    });
  }

  /* =========================
     DRAGGABLE FLOATING BUTTON
  ========================== */
  let isDragging = false;
  let offsetX = 0;
  let offsetY = 0;

  const startDrag = (e) => {
    isDragging = false;

    const rect = aiButton.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;

    offsetX = clientX - rect.left;
    offsetY = clientY - rect.top;

    aiButton.style.transition = "none";

    const moveHandler = (ev) => {
      isDragging = true;

      const x = ev.touches ? ev.touches[0].clientX : ev.clientX;
      const y = ev.touches ? ev.touches[0].clientY : ev.clientY;

      aiButton.style.left = x - offsetX + "px";
      aiButton.style.top = y - offsetY + "px";
      aiButton.style.right = "auto";
      aiButton.style.bottom = "auto";
    };

    const endHandler = () => {
      document.removeEventListener("mousemove", moveHandler);
      document.removeEventListener("mouseup", endHandler);
      document.removeEventListener("touchmove", moveHandler);
      document.removeEventListener("touchend", endHandler);

      aiButton.style.transition = "0.2s ease";
    };

    document.addEventListener("mousemove", moveHandler);
    document.addEventListener("mouseup", endHandler);
    document.addEventListener("touchmove", moveHandler);
    document.addEventListener("touchend", endHandler);
  };

  aiButton.addEventListener("mousedown", startDrag);
  aiButton.addEventListener("touchstart", startDrag);
});
