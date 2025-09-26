
def test_imports():
    import app.services.alpaca_client as ac
    import app.services.trader as tr
    import app.services.pricing as pr
    assert hasattr(ac, "AlpacaService")
    assert hasattr(tr, "TraderEngine")
    assert hasattr(pr, "compute_entry_limit")
