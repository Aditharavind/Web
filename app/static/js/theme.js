(function initializeTheme() {
  const storedTheme = localStorage.getItem("theme");
  // Default to light when nothing valid has been saved yet.
  const theme = storedTheme === "dark" ? "dark" : "light";

  function applyTheme(themeValue) {
    const nextTheme = themeValue === "dark" ? "dark" : "light";
    const isDark = nextTheme === "dark";

    document.documentElement.setAttribute("data-theme", nextTheme);

    if (document.body) {
      if (isDark) {
        document.body.classList.add("dark");
      } else {
        document.body.classList.remove("dark");
      }
    }

    document.querySelectorAll("[data-theme-toggle]").forEach((toggle) => {
      // Keep the visual switch state aligned with the active theme.
      toggle.checked = isDark;
      toggle.setAttribute("aria-pressed", String(isDark));
    });
  }

  applyTheme(theme);

  window.addEventListener("DOMContentLoaded", () => {
    applyTheme(theme);

    document.querySelectorAll("[data-theme-toggle]").forEach((toggle) => {
      toggle.addEventListener("click", () => {
        // Flip from the currently applied theme so the toggle works both ways.
        const currentTheme = document.documentElement.getAttribute("data-theme");
        const nextTheme = currentTheme === "dark" ? "light" : "dark";

        localStorage.setItem("theme", nextTheme);
        applyTheme(nextTheme);
      });
    });
  });
})();
