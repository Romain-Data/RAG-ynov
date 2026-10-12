// Additions to Chainlit's interface (only one custom_js file is allowed, see config.toml).
(function () {
  // Chainlit has no sign-up page: add the links to ours under the login form.
  const LINKS = [
    ["Créer un compte", "/compte/inscription"],
    ["Mot de passe oublié ?", "/compte/recuperation"],
  ];

  function addLinks() {
    if (!location.pathname.endsWith("/login")) return;
    if (document.getElementById("ynov-account-links")) return;
    const form = document.querySelector("form");
    if (!form) return;
    const box = document.createElement("div");
    box.id = "ynov-account-links";
    box.style.cssText =
      "margin-top:1rem;display:flex;flex-direction:column;gap:.5rem;text-align:center;font-size:.875rem";
    for (const [label, href] of LINKS) {
      const link = document.createElement("a");
      link.textContent = label;
      link.href = href;
      link.style.textDecoration = "underline";
      box.appendChild(link);
    }
    form.after(box);
  }

  // The user menu (the round button with the initial of the pseudo, top right) only holds
  // "Se déconnecter": add the account deletion page just above it. Chainlit 2.12.0 renders it
  // with Radix: while it is open, the button has aria-expanded="true" and aria-controls points
  // to the menu (role="menu"), mounted in a portal and removed when it closes. If that shape
  // changes, nothing is added and nothing breaks.
  const DELETE_ID = "ynov-delete-account";
  const TRASH_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="ml-auto" ' +
    'aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>' +
    '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';

  function addDeleteAccount() {
    const button = document.getElementById("user-nav-button");
    if (!button || button.getAttribute("aria-expanded") !== "true") return;
    const menuId = button.getAttribute("aria-controls");
    const menu = menuId && document.getElementById(menuId);
    if (!menu || menu.getAttribute("role") !== "menu") return;
    if (menu.querySelector("#" + DELETE_ID)) return;
    const items = menu.querySelectorAll('[role="menuitem"]');
    if (!items.length) return;
    const logout = items[items.length - 1];
    const link = document.createElement("a");
    link.id = DELETE_ID;
    link.href = "/compte/suppression";
    link.setAttribute("role", "menuitem");
    link.tabIndex = -1;
    link.className = logout.className;
    link.textContent = "Supprimer mon compte";
    link.insertAdjacentHTML("beforeend", TRASH_ICON);
    // Radix highlights its items by focusing them under the pointer (focus:bg-accent)
    link.addEventListener("pointermove", () => link.focus());
    link.addEventListener("pointerleave", () => menu.focus());
    // The arrow keys of Radix only know its own items: link the two entries by hand
    logout.addEventListener("keydown", (event) => {
      if (event.key === "ArrowUp") link.focus();
    });
    link.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        logout.focus();
      }
    });
    logout.before(link);
  }

  function update() {
    addLinks();
    addDeleteAccount();
  }

  // Both are rendered by React after the script has loaded, the menu each time it opens
  new MutationObserver(update).observe(document.documentElement, { childList: true, subtree: true });
  update();
})();
