"""Account pages, served next to the chat: /compte/inscription, /recuperation, /suppression."""
from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from app.core.security import rate_limit_account
from chat import accounts, pages

router = APIRouter(prefix="/compte", tags=["account"],
                   dependencies=[Depends(rate_limit_account)], include_in_schema=False)


def _html(content: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(content, status_code=status)


@router.get("/inscription")
def signup_page() -> HTMLResponse:
    return _html(pages.signup_form())


@router.post("/inscription")
def signup(pseudo: str = Form(""), password: str = Form(""),
           confirm: str = Form("")) -> HTMLResponse:
    try:
        if password != confirm:
            raise accounts.AccountError("Les deux mots de passe ne sont pas identiques.")
        code = accounts.register(pseudo, password)
    except accounts.AccountError as exc:
        return _html(pages.signup_form(str(exc), pseudo), 400)
    return _html(pages.code_page("Compte créé", f"Bienvenue, {pseudo.strip()} !", code))


@router.get("/recuperation")
def recover_page() -> HTMLResponse:
    return _html(pages.recover_form())


@router.post("/recuperation")
def recover(pseudo: str = Form(""), code: str = Form(""), password: str = Form(""),
            confirm: str = Form("")) -> HTMLResponse:
    try:
        if password != confirm:
            raise accounts.AccountError("Les deux mots de passe ne sont pas identiques.")
        new_code = accounts.recover(pseudo, code, password)
    except accounts.AccountError as exc:
        return _html(pages.recover_form(str(exc), pseudo), 400)
    return _html(pages.code_page("Mot de passe changé", "Votre mot de passe a été changé.",
                                 new_code))


@router.get("/suppression")
def delete_page() -> HTMLResponse:
    return _html(pages.delete_form())


@router.post("/suppression")
def delete(pseudo: str = Form(""), password: str = Form("")) -> HTMLResponse:
    try:
        accounts.delete_account(pseudo, password)
    except accounts.AccountError as exc:
        return _html(pages.delete_form(str(exc), pseudo), 400)
    return _html(pages.message_page("Compte supprimé",
                                    "Votre compte et vos conversations ont été supprimés."))
