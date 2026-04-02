window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-modal-open]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.querySelector(button.getAttribute("data-modal-open"));
      target?.classList.add("open");
    });
  });

  document.querySelectorAll("[data-modal-close]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.querySelector(button.getAttribute("data-modal-close"));
      target?.classList.remove("open");
    });
  });

  document.querySelectorAll("[data-upload-zone]").forEach((zone) => {
    const input = zone.querySelector("[data-upload-input]");
    if (!(input instanceof HTMLInputElement)) return;

    const renderPreview = () => {
      const previewId = input.dataset.previewTarget;
      if (!previewId) return;
      const grid = document.getElementById(previewId);
      if (!grid) return;

      grid.innerHTML = "";
      Array.from(input.files || [])
        .slice(0, 10)
        .forEach((file, index) => {
          const reader = new FileReader();
          reader.onload = (event) => {
            const item = document.createElement("div");
            item.className = "img-preview-item";
            item.innerHTML = `<img src="${event.target?.result || ""}" alt="">${
              index === 0 ? '<span class="primary-badge">PRIMARY</span>' : ""
            }`;
            grid.appendChild(item);
          };
          reader.readAsDataURL(file);
        });
    };

    input.addEventListener("change", renderPreview);
    zone.addEventListener("dragover", (event) => {
      event.preventDefault();
      zone.classList.add("dragover");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      zone.classList.remove("dragover");
      if (!(event.dataTransfer && input)) return;
      input.files = event.dataTransfer.files;
      renderPreview();
    });
  });
});
