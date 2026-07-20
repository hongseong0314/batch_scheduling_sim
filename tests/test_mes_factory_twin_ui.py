from fastapi.testclient import TestClient

from src.mes.api import app


def test_mes_shell_mounts_factory_twin_page_and_bundle():
    client = TestClient(app)
    html = client.get("/mes").text

    assert 'href="#factory-twin"' in html
    assert 'id="factory-twin-page"' in html
    assert '/static/mes/dist/factory-twin.js' in html
    assert client.get("/static/mes/dist/factory-twin.js").status_code == 200
