/**
 * Pre-hydration theme resolver, injected as an inline <script> in the root layout.
 *
 * Runs before first paint so there is no light/dark flash:
 *   1. use the persisted choice in localStorage if present, else
 *   2. fall back to the OS `prefers-color-scheme`.
 * Kept as a stringified IIFE because inline scripts cannot import modules.
 */
export const themeScript = `(function () {
  try {
    var stored = window.localStorage.getItem("mimik-theme");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var theme = stored === "light" || stored === "dark" ? stored : (prefersDark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();`;
