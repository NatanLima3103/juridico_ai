import threading
import time
from collections import deque


class SlidingWindowLimiter:
    """Conta eventos por chave dentro de uma janela de tempo.

    Fica em memoria do processo: vale para a stack atual, que roda um unico
    worker do Uvicorn. Com varios workers ou instancias, cada um tera sua
    propria contagem e o limite precisa ir para um armazenamento compartilhado.
    """

    def __init__(self, *, max_events: int, window_seconds: int) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _purge(self, key: str, now: float) -> deque[float]:
        eventos = self._events.get(key)
        if eventos is None:
            return deque()
        limite = now - self.window_seconds
        while eventos and eventos[0] <= limite:
            eventos.popleft()
        if not eventos:
            self._events.pop(key, None)
        return eventos

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._purge(key, time.monotonic())) >= self.max_events

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._purge(key, now)
            self._events.setdefault(key, deque()).append(now)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)


# Falhas de login por e-mail e por IP; o limite por IP e mais alto para nao
# bloquear escritorios inteiros atras do mesmo endereco.
login_failures_by_email = SlidingWindowLimiter(max_events=5, window_seconds=15 * 60)
login_failures_by_ip = SlidingWindowLimiter(max_events=20, window_seconds=15 * 60)
# Pedidos de recuperacao de senha e cadastros por IP.
password_reset_requests_by_ip = SlidingWindowLimiter(max_events=5, window_seconds=15 * 60)
registrations_by_ip = SlidingWindowLimiter(max_events=10, window_seconds=60 * 60)

ALL_LIMITERS = (
    login_failures_by_email,
    login_failures_by_ip,
    password_reset_requests_by_ip,
    registrations_by_ip,
)


def client_ip(request) -> str:
    # O Uvicorn so confia em X-Forwarded-For quando iniciado com --proxy-headers;
    # aqui usamos o endereco que ele ja resolveu.
    client = getattr(request, "client", None)
    return getattr(client, "host", None) or "desconhecido"


def reset_all_limiters() -> None:
    for limiter in ALL_LIMITERS:
        limiter.reset()
