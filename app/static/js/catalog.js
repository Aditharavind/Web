window.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector("[data-catalog-search]");
  const categories = Array.from(document.querySelectorAll("[data-catalog-category]"));
  const form = document.getElementById("catalog-form");
  if (!input || !form) return;

  let timeoutId;
  input.addEventListener("input", (event) => {
    window.clearTimeout(timeoutId);
    if (event.isComposing) return;
    timeoutId = window.setTimeout(() => form.requestSubmit(), 450);
  });

  categories.forEach((category) => {
    category.addEventListener("change", () => {
      window.clearTimeout(timeoutId);
      form.requestSubmit();
    });
  });

  const dropdown = document.querySelector?.(".filter-dropdown");
  if (dropdown && document.addEventListener) {
    // Measured only when the visitor opens the list, never while the page loads.
    dropdown.addEventListener("toggle", () => {
      const panel = dropdown.querySelector(".filter-panel");
      if (!panel) return;
      panel.classList.remove("align-end");
      if (dropdown.open && panel.getBoundingClientRect().right > document.documentElement.clientWidth - 8) {
        panel.classList.add("align-end");
      }
    });
    document.addEventListener("click", (event) => {
      if (dropdown.open && !dropdown.contains(event.target)) dropdown.open = false;
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") dropdown.open = false;
    });
  }
});
