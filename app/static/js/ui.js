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

  document.querySelectorAll("[data-confirm]").forEach((element) => {
    element.addEventListener("click", (event) => {
      const message = element.getAttribute("data-confirm") || "Are you sure?";
      if (!window.confirm(message)) {
        event.preventDefault();
      }
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
