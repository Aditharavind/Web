window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-nav-toggle]").forEach((button) => {
    const nav = button.closest(".navbar");
    const controlsId = button.getAttribute("aria-controls");
    const controlledNav = controlsId ? document.getElementById(controlsId) : null;

    const setOpenState = (isOpen) => {
      if (!nav) return;
      nav.classList.toggle("mobile-open", isOpen);
      button.setAttribute("aria-expanded", String(isOpen));
      if (controlledNav) {
        controlledNav.setAttribute("aria-hidden", String(!isOpen));
      }
    };

    button.addEventListener("click", () => {
      if (!nav) return;
      setOpenState(!nav.classList.contains("mobile-open"));
    });

    nav?.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => setOpenState(false));
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 900) {
        setOpenState(false);
      }
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
});
