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
        data={
            "host": "172.17.57.240",
            "interface": "Gi1/0/48",
            "new_vlan": "10",  # Corrected key,
            "description": "Test VLAN change"
        }
    )
    assert response.status_code == 200
    json_data = response.json()
    assert "message" in json_data
    assert "Successfully changed" in json_data["message"]


def test_get_mac_address_success():
    response = client.get("/find-mac?mac=300a.60a0.324b")    
    assert response.status_code == 200


  



