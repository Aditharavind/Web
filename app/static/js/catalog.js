window.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector("[data-catalog-search]");
  const category = document.querySelector("[data-catalog-category]");
  const form = document.getElementById("catalog-form");
  if (!input || !form) return;

  let timeoutId;
  input.addEventListener("input", () => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => form.submit(), 450);
  });

  category?.addEventListener("change", () => form.submit());
});
