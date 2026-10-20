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
    document.addEventListener("click", (event) => {
      if (dropdown.open && !dropdown.contains(event.target)) dropdown.open = false;
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") dropdown.open = false;
    });
  }
});
