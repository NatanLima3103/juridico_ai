from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def _hostname(value: str | None) -> str | None:
    if not value:
        return None
    if "://" not in value:
        value = f"//{value}"
    try:
        return (urlsplit(value).hostname or "").lower() or None
    except ValueError:
        return None


def is_same_origin_request(headers: Headers) -> bool:
    # Navegadores atuais enviam Sec-Fetch-Site em toda requisicao; e o sinal mais confiavel.
    fetch_site = headers.get("sec-fetch-site")
    if fetch_site is not None:
        return fetch_site in {"same-origin", "none"}

    host = _hostname(headers.get("x-forwarded-host") or headers.get("host"))

    # Compara so o nome do host: atras do proxy o Host pode chegar sem a porta publica.
    origin = headers.get("origin")
    if origin is not None:
        return origin != "null" and _hostname(origin) == host

    referer = headers.get("referer")
    if referer is not None:
        return _hostname(referer) == host

    # Sem nenhum desses cabecalhos nao veio de um navegador (curl, testes, integracoes);
    # o cookie de sessao com SameSite=Lax ja impede que ele seja usado por outro site.
    return True


class OriginCheckMiddleware:
    """Recusa requisicoes que alteram dados quando vem de outro site (CSRF)."""

    def __init__(self, app: ASGIApp, *, exempt_paths: set[str] | None = None) -> None:
        self.app = app
        self.exempt_paths = exempt_paths or set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] not in SAFE_METHODS
            and scope["path"] not in self.exempt_paths
            and not is_same_origin_request(Headers(scope=scope))
        ):
            response = PlainTextResponse(
                "Requisição bloqueada: origem não permitida.",
                status_code=403,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
