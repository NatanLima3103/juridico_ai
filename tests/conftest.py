import pytest

from app.core.rate_limit import reset_all_limiters


@pytest.fixture(autouse=True)
def _limpar_limites_de_tentativas():
    # Os limitadores ficam em memoria no modulo; sem isso um teste herdaria
    # as tentativas registradas pelos anteriores.
    reset_all_limiters()
    yield
    reset_all_limiters()
