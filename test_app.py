from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_get_config_success():
    response = client.get("/get-config?hostname=172.17.57.240")
    assert response.status_code == 200
    assert "Configuration for 172.17.57.240" in response.text

def test_change_vlan():
    response = client.post(
        "/change-vlan",
        data={"host": "172.17.57.240", "interface": "Gi1/0/1", "new_vlan": "100"}
    )
    assert response.status_code == 200
    assert "Successfully changed" in response.json()["message"]