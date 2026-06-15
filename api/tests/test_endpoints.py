import pytest

@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "orchard-brain-api"}

@pytest.mark.asyncio
async def test_get_sensor_history_empty(client):
    response = await client.get("/sensor-history")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_get_recommendations_empty(client):
    response = await client.get("/recommendations")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_get_nodes_empty(client):
    response = await client.get("/nodes")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_dispatch_command(client):
    cmd_data = {
        "command_id": "cmd-123",
        "target_node": 10,
        "actuator_type": 1,
        "action": 1,
        "value": 100.0,
        "duration_sec": 30
    }
    response = await client.post("/commands", json=cmd_data)
    assert response.status_code == 202
    assert response.json() == {"status": "QUEUED", "command_id": "cmd-123"}

@pytest.mark.asyncio
async def test_push_configuration(client):
    conf_data = {
        "config_hash": 123456,
        "lora_channel": 8,
        "tx_power_dbm": 14,
        "sample_rate_sec": 60
    }
    response = await client.post("/configuration", json=conf_data)
    assert response.status_code == 202
    assert response.json()["status"] == "QUEUED"
