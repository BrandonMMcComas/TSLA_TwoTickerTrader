import pytest


def test_imports():
    pytest.importorskip("alpaca.trading.client")

    import app.services.alpaca_client as ac
    import app.services.pricing as pr
    import app.services.trader as tr

    assert hasattr(ac, "AlpacaService")
    assert hasattr(tr, "TraderEngine")
    assert hasattr(pr, "compute_entry_limit")
