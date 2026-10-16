window.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector("[data-catalog-search]");
  const category = document.querySelector("[data-catalog-category]");
  const form = document.getElementById("catalog-form");
  if (!input || !form) return;

  let timeoutId;
  input.addEventListener("input", (event) => {
    window.clearTimeout(timeoutId);
    if (event.isComposing) return;
    timeoutId = window.setTimeout(() => form.requestSubmit(), 450);
  });

  category?.addEventListener("change", () => {
    window.clearTimeout(timeoutId);
    form.requestSubmit();
  });
});
