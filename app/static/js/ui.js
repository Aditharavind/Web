window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-nav-toggle]").forEach((button) => {
    const nav = button.closest(".navbar");
    const controlsId = button.getAttribute("aria-controls");
    const controlledNav = controlsId
      ? document.getElementById(controlsId)
      : null;

    const setOpenState = (isOpen) => {
      if (!nav) return;
      nav.classList.toggle("mobile-open", isOpen);
      button.setAttribute("aria-expanded", String(isOpen));
      if (controlledNav) {
        controlledNav.setAttribute(
          "aria-hidden",
          String(!isOpen && window.innerWidth <= 900),
        );
      }
    };

    setOpenState(false);

    button.addEventListener("click", () => {
      if (!nav) return;
      setOpenState(!nav.classList.contains("mobile-open"));
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setOpenState(false);
    });

    nav?.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => setOpenState(false));
    });

    window.addEventListener("resize", () => {
      setOpenState(window.innerWidth <= 900 && nav?.classList.contains("mobile-open"));
    });
  });

  const askConfirm = (message) =>
    new Promise((resolve) => {
      const previous = document.activeElement;
      const overlay = document.createElement("div");
      overlay.className = "confirm-overlay";
      const box = document.createElement("div");
      box.className = "confirm-box";
      box.setAttribute("role", "alertdialog");
      box.setAttribute("aria-modal", "true");
      const text = document.createElement("p");
      text.textContent = message;
      const row = document.createElement("div");
      row.className = "confirm-actions";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "btn";
      cancel.textContent = "Cancel";
      const ok = document.createElement("button");
      ok.type = "button";
      ok.className = "btn danger";
      ok.textContent = "Yes, continue";
      const close = (result) => {
        document.removeEventListener("keydown", onKey);
        overlay.remove();
        if (previous && previous.focus) previous.focus();
        resolve(result);
      };
      const onKey = (event) => {
        if (event.key === "Escape") close(false);
      };
      cancel.addEventListener("click", () => close(false));
      ok.addEventListener("click", () => close(true));
      overlay.addEventListener("click", (event) => {
        if (event.target === overlay) close(false);
      });
      document.addEventListener("keydown", onKey);
      row.append(cancel, ok);
      box.append(text, row);
      overlay.append(box);
      document.body.append(overlay);
      cancel.focus();
    });

  document.querySelectorAll("[data-confirm]").forEach((element) => {
    element.addEventListener("click", (event) => {
      if (element.dataset.confirmed === "1") {
        delete element.dataset.confirmed;
        return;
      }
      event.preventDefault();
      askConfirm(element.getAttribute("data-confirm") || "Are you sure?").then(
        (accepted) => {
          if (!accepted) return;
          element.dataset.confirmed = "1";
          element.click();
        },
      );
    });
  });

  document.querySelectorAll("[data-height]").forEach((element) => {
    const height = element.getAttribute("data-height");
    if (height) {
      element.style.height = `${height}%`;
    }
  });

  document.querySelectorAll("[data-card-gallery]").forEach((gallery) => {
    const image = gallery.querySelector("[data-card-image]");
    const counter = gallery.querySelector("[data-card-counter]");
    if (!image || !counter) return;

    let images = [];
    try {
      const parsed = JSON.parse(image.dataset.images || "[]");
      images = Array.isArray(parsed) ? parsed.filter(Boolean) : [];
    } catch {
      return;
    }
    if (images.length < 2) return;

    let index = 0;
    gallery.querySelectorAll("[data-card-step]").forEach((button) => {
      button.addEventListener("click", () => {
        index = (index + Number(button.dataset.cardStep) + images.length) % images.length;
        image.src = `/uploads/${images[index]}`;
        image.alt = `Product image ${index + 1}`;
        counter.textContent = `${index + 1} / ${images.length}`;
      });
    });
  });
});
