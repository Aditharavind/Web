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

    const maxFiles = Number(zone.dataset.maxFiles) || 10;
    const maxBytes = Number(zone.dataset.maxBytes) || 0;
    const existing = Number(zone.dataset.existing) || 0;
    const note = zone.parentElement?.querySelector("[data-upload-error]");
    const allowed = /\.(jpe?g|png|webp)$/i;

    const showProblem = (text) => {
      if (!note) return;
      note.textContent = text;
      note.hidden = !text;
    };

    // Same rules the server enforces, checked before anything is sent.
    const problemWith = (files) => {
      if (files.some((file) => !allowed.test(file.name))) return "Only JPG, PNG or WEBP images can be uploaded.";
      if (maxBytes && files.some((file) => file.size > maxBytes)) {
        return `Each image must be ${(maxBytes / 1048576).toFixed(1)} MB or smaller.`;
      }
      if (existing + files.length > maxFiles) {
        return existing
          ? `A product can have up to ${maxFiles} images and already has ${existing}.`
          : `You can upload up to ${maxFiles} images per product.`;
      }
      return "";
    };

    const previewUrls = new Set();
    const releasePreviewUrls = () => {
      previewUrls.forEach((url) => URL.revokeObjectURL(url));
      previewUrls.clear();
    };
    window.addEventListener("pagehide", releasePreviewUrls);

    const grid = document.getElementById(input.dataset.previewTarget || "");
    const renderPreview = () => {
      if (!grid) return;
      releasePreviewUrls();
      grid.replaceChildren();
      Array.from(input.files || []).forEach((file, index) => {
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
        if (index === 0 && !existing) {
          const badge = document.createElement("span");
          badge.className = "primary-badge";
          badge.textContent = "PRIMARY";
          item.appendChild(badge);
        }
        grid.appendChild(item);
      });
    };

    const accept = (list, dropped) => {
      const files = Array.from(list || []);
      const problem = problemWith(files);
      showProblem(problem);
      if (problem) {
        input.value = "";  // nothing invalid is ever submitted
      } else if (dropped) {
        const transfer = new DataTransfer();
        files.forEach((file) => transfer.items.add(file));
        input.files = transfer.files;
      }
      renderPreview();
    };

    input.addEventListener("change", () => accept(input.files));
    zone.addEventListener("dragover", (event) => {
      event.preventDefault();
      zone.classList.add("dragover");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      zone.classList.remove("dragover");
      if (event.dataTransfer) accept(event.dataTransfer.files, true);
    });
  });

  // One click submits once: a slow upload can no longer create a product twice.
  document.querySelectorAll("form[enctype='multipart/form-data']").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (form.dataset.sending) {
        event.preventDefault();
        return;
      }
      form.dataset.sending = "1";
      form.querySelectorAll("button[type='submit']:not([form])").forEach((button) => {
        button.disabled = true;
        button.textContent = "Please wait…";
      });
    });
  });
  // Coming back with the Back button must not leave the form stuck.
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) window.location.reload();
  });

  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) overlay.classList.remove("open");
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".modal-overlay.open").forEach((overlay) => overlay.classList.remove("open"));
  });

  const search = document.querySelector("[data-admin-search]");
  const category = document.querySelector("[data-admin-category]");
  if (search || category) {
    const rows = Array.from(document.querySelectorAll("[data-admin-row]"));
    const empty = document.querySelector("[data-admin-empty]");
    const applyFilter = () => {
      const term = (search ? search.value : "").trim().toLowerCase();
      const wanted = category ? category.value : "";
      let visible = 0;
      rows.forEach((row) => {
        const match =
          (!term || (row.dataset.name || "").includes(term)) &&
          (!wanted || row.dataset.category === wanted);
        row.hidden = !match;
        if (match) visible += 1;
      });
      if (empty) empty.hidden = visible > 0;
    };
    search?.addEventListener("input", applyFilter);
    category?.addEventListener("change", applyFilter);
  }
});
