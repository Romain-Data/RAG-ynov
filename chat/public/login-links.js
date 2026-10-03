// Chainlit has no sign-up page: add the links to ours under the login form.
(function () {
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

  // The login form is rendered by React after the script has loaded
  new MutationObserver(addLinks).observe(document.documentElement, { childList: true, subtree: true });
  addLinks();
})();
