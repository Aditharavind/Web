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

    const previewUrls = new Set();
    const releasePreviewUrls = () => {
      previewUrls.forEach((url) => URL.revokeObjectURL(url));
      previewUrls.clear();
    };
    window.addEventListener("pagehide", releasePreviewUrls);

    const renderPreview = () => {
      const previewId = input.dataset.previewTarget;
      if (!previewId) return;
      const grid = document.getElementById(previewId);
      if (!grid) return;

      releasePreviewUrls();
      grid.replaceChildren();
      Array.from(input.files || [])
        .slice(0, 10)
        .forEach((file, index) => {
          const item = document.createElement("div");
          item.className = "img-preview-item";
          const image = document.createElement("img");
          const url = URL.createObjectURL(file);
          previewUrls.add(url);
          const release = () => {
            URL.revokeObjectURL(url);
            previewUrls.delete(url);
          };
          image.addEventListener("load", release, { once: true });
          image.addEventListener("error", release, { once: true });
          image.src = url;
          image.alt = `Selected upload ${index + 1}`;
          item.appendChild(image);
          if (index === 0) {
            const badge = document.createElement("span");
            badge.className = "primary-badge";
            badge.textContent = "PRIMARY";
            item.appendChild(badge);
          }
          grid.appendChild(item);
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
