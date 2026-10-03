"""HTML of the account pages: sign-up, recovery and deletion (Chainlit has none)."""
from html import escape

_STYLE = """
:root { color-scheme: light dark; --accent: #2a4bb0; --bg: #f4f6fb; --card: #fff;
        --text: #141a2e; --muted: #5b6480; --border: #d5dae8; --error: #b3261e; }
@media (prefers-color-scheme: dark) {
  :root { --accent: #7d9bff; --bg: #10142a; --card: #181d38; --text: #f1f3fb;
          --muted: #a6aecb; --border: #2d3458; --error: #ff8a80; } }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 16px;
       font-family: Inter, system-ui, sans-serif; background: var(--bg); color: var(--text); }
main { width: 100%; max-width: 420px; background: var(--card); border: 1px solid var(--border);
       border-radius: 12px; padding: 28px; }
h1 { font-size: 1.35rem; margin: 0 0 .5rem; }
p, li { color: var(--muted); font-size: .9rem; line-height: 1.5; }
label { display: block; margin: 1rem 0 .25rem; font-size: .85rem; font-weight: 600; }
input[type=text], input[type=password] { width: 100%; padding: .6rem .7rem; font-size: 1rem;
       border: 1px solid var(--border); border-radius: 8px; background: transparent;
       color: inherit; }
button { margin-top: 1.25rem; width: 100%; padding: .7rem; border: 0; border-radius: 8px;
         background: var(--accent); color: #fff; font-size: 1rem; cursor: pointer; }
button.danger { background: var(--error); }
a { color: var(--accent); }
.error { color: var(--error); font-weight: 600; font-size: .9rem; }
.code { font: 600 1.25rem ui-monospace, monospace; letter-spacing: .08em; text-align: center;
        padding: .9rem; border: 2px dashed var(--accent); border-radius: 8px; margin: 1rem 0;
        user-select: all; }
.links { margin-top: 1.25rem; display: flex; flex-direction: column; gap: .4rem;
         font-size: .875rem; text-align: center; }
"""


def page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)} — Assistant Ynov</title><style>{_STYLE}</style></head>"
        f"<body><main><h1>{escape(title)}</h1>{body}</main></body></html>"
    )


def _error(message: str | None) -> str:
    return f'<p class="error" role="alert">{escape(message)}</p>' if message else ""


def _field(name: str, label: str, kind: str = "text", value: str = "",
           autocomplete: str = "off") -> str:
    return (f'<label for="{name}">{escape(label)}</label>'
            f'<input id="{name}" name="{name}" type="{kind}" value="{escape(value)}" '
            f'autocomplete="{autocomplete}" required>')


LOGIN_LINK = '<div class="links"><a href="/chat/login">Retour à la connexion</a></div>'


def signup_form(error: str | None = None, pseudo: str = "") -> str:
    return page("Créer un compte", (
        "<p>Un pseudo et un mot de passe suffisent : ni e-mail, ni nom. Évitez d'utiliser "
        "votre vrai nom comme pseudo.</p>" + _error(error) +
        '<form method="post">' + _field("pseudo", "Pseudo", value=pseudo, autocomplete="username") +
        _field("password", "Mot de passe (8 caractères minimum)", "password",
               autocomplete="new-password") +
        _field("confirm", "Confirmez le mot de passe", "password", autocomplete="new-password") +
        "<button>Créer mon compte</button></form>" + LOGIN_LINK))


def code_page(title: str, intro: str, code: str) -> str:
    return page(title, (
        f"<p>{escape(intro)}</p>"
        "<p><strong>Voici votre code de secours. Notez-le maintenant : il ne sera plus "
        "affiché.</strong> Sans e-mail, c'est le seul moyen de retrouver votre compte si vous "
        "oubliez votre mot de passe.</p>"
        f'<div class="code">{escape(code)}</div>'
        '<div class="links"><a href="/chat/login">Se connecter</a></div>'))


def recover_form(error: str | None = None, pseudo: str = "") -> str:
    return page("Mot de passe oublié", (
        "<p>Entrez votre pseudo, le code de secours reçu à l'inscription et un nouveau mot de "
        "passe. Un nouveau code de secours vous sera donné.</p>" + _error(error) +
        '<form method="post">' + _field("pseudo", "Pseudo", value=pseudo, autocomplete="username") +
        _field("code", "Code de secours") +
        _field("password", "Nouveau mot de passe", "password", autocomplete="new-password") +
        _field("confirm", "Confirmez le nouveau mot de passe", "password",
               autocomplete="new-password") +
        "<button>Changer mon mot de passe</button></form>" + LOGIN_LINK))


def delete_form(error: str | None = None, pseudo: str = "") -> str:
    return page("Supprimer mon compte", (
        "<p>Votre compte et toutes vos conversations seront supprimés définitivement. "
        "Cette action est irréversible.</p>" + _error(error) +
        '<form method="post">' + _field("pseudo", "Pseudo", value=pseudo, autocomplete="username") +
        _field("password", "Mot de passe", "password", autocomplete="current-password") +
        '<button class="danger">Supprimer définitivement</button></form>'
        '<div class="links"><a href="/chat/">Retour au chat</a></div>'))


def message_page(title: str, text: str) -> str:
    return page(title, f"<p>{escape(text)}</p>" + LOGIN_LINK)
