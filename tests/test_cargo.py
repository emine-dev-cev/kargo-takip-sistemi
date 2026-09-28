import os
import tempfile
import pytest
from app import create_app
from app.models import (
    init_db,
    create_cargo,
    get_cargo_by_id,
    get_all_cargos,
    update_cargo_status,
    delete_cargo
)

@pytest.fixture
def app_client():
    """Create and configure a clean testing app instance and client with temporary SQLite db."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    
    test_config = {
        'TESTING': True,
        'DATABASE_PATH': db_path,
        'KAFKA_BOOTSTRAP_SERVERS': None
    }
    
    app = create_app(test_config)
    with app.test_client() as client:
        with app.app_context():
            yield client, db_path

    os.close(db_fd)
    if os.path.exists(db_path):
        os.remove(db_path)


# -------------------------------------------------------------
# 1. create_cargo() Tests
# -------------------------------------------------------------

def test_create_cargo_success(app_client):
    """Scenario 1: Geçerli bilgilerle kargo oluşturulabiliyor mu?"""
    client, db_path = app_client
    payload = {
        "tracking_number": "KRG-1001",
        "sender": "Ahmet Yılmaz",
        "receiver": "Mehmet Demir"
    }
    response = client.post('/cargo', json=payload)
    assert response.status_code == 201
    
    data = response.get_json()
    assert "id" in data
    assert data["tracking_number"] == "KRG-1001"
    assert data["sender"] == "Ahmet Yılmaz"
    assert data["receiver"] == "Mehmet Demir"
    assert data["status"] == "CREATED"
    assert "created_at" in data

def test_create_cargo_empty_tracking_number(app_client):
    """Scenario 2: Tracking number boş bırakıldığında hata veriliyor mu?"""
    client, db_path = app_client
    payload = {
        "tracking_number": "",
        "sender": "Ahmet Yılmaz",
        "receiver": "Mehmet Demir"
    }
    response = client.post('/cargo', json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data

def test_create_cargo_missing_fields(app_client):
    """Test validation when sender or receiver is missing or empty."""
    client, db_path = app_client
    # Missing sender
    response = client.post('/cargo', json={"tracking_number": "KRG-1002", "receiver": "Mehmet"})
    assert response.status_code == 400

    # Missing receiver
    response = client.post('/cargo', json={"tracking_number": "KRG-1003", "sender": "Ahmet"})
    assert response.status_code == 400

def test_create_cargo_duplicate_tracking_number(app_client):
    """Test validation when same tracking number is submitted twice."""
    client, db_path = app_client
    payload = {
        "tracking_number": "KRG-UNIQUE-1",
        "sender": "Ali",
        "receiver": "Veli"
    }
    res1 = client.post('/cargo', json=payload)
    assert res1.status_code == 201

    res2 = client.post('/cargo', json=payload)
    assert res2.status_code == 400
    data = res2.get_json()
    assert "already exists" in data.get("error", "").lower()


# -------------------------------------------------------------
# 2. get_cargo() Tests
# -------------------------------------------------------------

def test_get_cargo_not_found(app_client):
    """Scenario 3: Olmayan kargo sorgulandığında HTTP 404 dönüyor mu?"""
    client, db_path = app_client
    response = client.get('/cargo/999999')
    assert response.status_code == 404
    data = response.get_json()
    assert data.get("error") == "Cargo not found"

def test_get_cargo_by_id_success(app_client):
    """Test retrieving existing cargo by ID."""
    client, db_path = app_client
    create_res = client.post('/cargo', json={
        "tracking_number": "KRG-GET-1",
        "sender": "Can",
        "receiver": "Cem"
    })
    cargo_id = create_res.get_json()["id"]

    get_res = client.get(f'/cargo/{cargo_id}')
    assert get_res.status_code == 200
    data = get_res.get_json()
    assert data["id"] == cargo_id
    assert data["tracking_number"] == "KRG-GET-1"

def test_get_all_cargos(app_client):
    """Test retrieving list of all cargos."""
    client, db_path = app_client
    client.post('/cargo', json={"tracking_number": "KRG-ALL-1", "sender": "A", "receiver": "B"})
    client.post('/cargo', json={"tracking_number": "KRG-ALL-2", "sender": "C", "receiver": "D"})

    response = client.get('/cargo')
    assert response.status_code == 200
    cargos = response.get_json()
    assert isinstance(cargos, list)
    assert len(cargos) >= 2


# -------------------------------------------------------------
# 3. update_status() Tests
# -------------------------------------------------------------

def test_update_cargo_status_success(app_client):
    """Scenario 4: Kargo durumu değiştirilebiliyor mu?"""
    client, db_path = app_client
    create_res = client.post('/cargo', json={
        "tracking_number": "KRG-STATUS-1",
        "sender": "Ayşe",
        "receiver": "Fatma"
    })
    cargo_id = create_res.get_json()["id"]

    # Change to IN_TRANSIT
    update_res = client.put(f'/cargo/{cargo_id}/status', json={"status": "IN_TRANSIT"})
    assert update_res.status_code == 200
    assert update_res.get_json()["status"] == "IN_TRANSIT"

    # Change to OUT_FOR_DELIVERY
    update_res2 = client.put(f'/cargo/{cargo_id}/status', json={"status": "OUT_FOR_DELIVERY"})
    assert update_res2.status_code == 200
    assert update_res2.get_json()["status"] == "OUT_FOR_DELIVERY"

def test_update_cargo_invalid_status(app_client):
    """Scenario 5: Geçersiz durum gönderildiğinde hata dönüyor mu?"""
    client, db_path = app_client
    create_res = client.post('/cargo', json={
        "tracking_number": "KRG-STATUS-INV",
        "sender": "Ayşe",
        "receiver": "Fatma"
    })
    cargo_id = create_res.get_json()["id"]

    response = client.put(f'/cargo/{cargo_id}/status', json={"status": "INVALID_STATUS_TEST"})
    assert response.status_code == 400
    data = response.get_json()
    assert "Invalid status" in data.get("error", "")

def test_update_status_delivered_cannot_revert(app_client):
    """Scenario 6: DELIVERED kargo tekrar dağıtıma çıkarılabiliyor mu? Çıkarılamamalı."""
    client, db_path = app_client
    create_res = client.post('/cargo', json={
        "tracking_number": "KRG-DELIVERED-TEST",
        "sender": "Kemal",
        "receiver": "Leman"
    })
    cargo_id = create_res.get_json()["id"]

    # Mark as DELIVERED
    deliv_res = client.put(f'/cargo/{cargo_id}/status', json={"status": "DELIVERED"})
    assert deliv_res.status_code == 200
    assert deliv_res.get_json()["status"] == "DELIVERED"

    # Try changing back to OUT_FOR_DELIVERY or IN_TRANSIT
    revert_res = client.put(f'/cargo/{cargo_id}/status', json={"status": "OUT_FOR_DELIVERY"})
    assert revert_res.status_code == 400
    data = revert_res.get_json()
    assert "cannot change status" in data.get("error", "").lower()

def test_update_status_cancelled_cannot_change(app_client):
    """Scenario: CANCELLED kargo durumu tekrar değiştirilememeli."""
    client, db_path = app_client
    create_res = client.post('/cargo', json={
        "tracking_number": "KRG-CANCELLED-TEST",
        "sender": "Kemal",
        "receiver": "Leman"
    })
    cargo_id = create_res.get_json()["id"]

    # Mark as CANCELLED
    cancel_res = client.put(f'/cargo/{cargo_id}/status', json={"status": "CANCELLED"})
    assert cancel_res.status_code == 200
    assert cancel_res.get_json()["status"] == "CANCELLED"

    # Try changing to SHIPPED
    revert_res = client.put(f'/cargo/{cargo_id}/status', json={"status": "SHIPPED"})
    assert revert_res.status_code == 400


# -------------------------------------------------------------
# 4. delete_cargo() Tests
# -------------------------------------------------------------

def test_delete_cargo_success(app_client):
    """Scenario 7: Kargo silinebiliyor mu?"""
    client, db_path = app_client
    create_res = client.post('/cargo', json={
        "tracking_number": "KRG-DEL-1",
        "sender": "Murat",
        "receiver": "Selim"
    })
    cargo_id = create_res.get_json()["id"]

    # Delete
    del_res = client.delete(f'/cargo/{cargo_id}')
    assert del_res.status_code == 200
    assert "deleted successfully" in del_res.get_json().get("message", "").lower()

def test_delete_cargo_not_found_after_deletion(app_client):
    """Scenario 8: Silinen kargo tekrar sorgulandığında 404 dönüyor mu?"""
    client, db_path = app_client
    create_res = client.post('/cargo', json={
        "tracking_number": "KRG-DEL-2",
        "sender": "Murat",
        "receiver": "Selim"
    })
    cargo_id = create_res.get_json()["id"]

    # Delete
    del_res = client.delete(f'/cargo/{cargo_id}')
    assert del_res.status_code == 200

    # Query again
    get_res = client.get(f'/cargo/{cargo_id}')
    assert get_res.status_code == 404
    assert get_res.get_json().get("error") == "Cargo not found"


# -------------------------------------------------------------
# 5. Metrics & Direct Model Tests
# -------------------------------------------------------------

def test_prometheus_metrics_endpoint(app_client):
    """Test Prometheus metrics endpoint /metrics."""
    client, db_path = app_client
    # Perform some actions
    client.post('/cargo', json={"tracking_number": "KRG-METRIC-1", "sender": "S", "receiver": "R"})
    
    response = client.get('/metrics')
    assert response.status_code == 200
    metrics_data = response.data.decode('utf-8')
    assert "cargo_created_total" in metrics_data
    assert "api_request_total" in metrics_data

def test_direct_model_functions(tmp_path):
    """Direct testing of models.py CRUD functions."""
    db_file = str(tmp_path / "test_direct.db")
    init_db(db_file)

    cargo = create_cargo("DIRECT-1", "Sender1", "Recv1", db_file)
    assert cargo["id"] == 1
    assert cargo["status"] == "CREATED"

    fetched = get_cargo_by_id(1, db_file)
    assert fetched["tracking_number"] == "DIRECT-1"

    updated = update_cargo_status(1, "SHIPPED", db_file)
    assert updated["status"] == "SHIPPED"

    all_cargos = get_all_cargos(db_file)
    assert len(all_cargos) == 1

    deleted = delete_cargo(1, db_file)
    assert deleted is True

    assert get_cargo_by_id(1, db_file) is None

def test_full_scenario_execution(app_client):
    """Scenario 13: Full 20-cargo simulation scenario test."""
    client, db_path = app_client

    # 1. 20 adet kargo oluştur
    created_ids = []
    for i in range(1, 21):
        res = client.post('/cargo', json={
            "tracking_number": f"SCENARIO-KRG-{1000+i}",
            "sender": f"Sender-{i}",
            "receiver": f"Receiver-{i}"
        })
        assert res.status_code == 201
        created_ids.append(res.get_json()["id"])
    assert len(created_ids) == 20

    # 2. 10 kargonun durumunu IN_TRANSIT yap
    for cid in created_ids[:10]:
        res = client.put(f'/cargo/{cid}/status', json={"status": "IN_TRANSIT"})
        assert res.status_code == 200
        assert res.get_json()["status"] == "IN_TRANSIT"

    # 3. 5 kargoyu DELIVERED durumuna getir
    for cid in created_ids[:5]:
        res = client.put(f'/cargo/{cid}/status', json={"status": "DELIVERED"})
        assert res.status_code == 200
        assert res.get_json()["status"] == "DELIVERED"

    # 4. 2 kargoyu CANCELLED yap
    for cid in created_ids[18:20]:
        res = client.put(f'/cargo/{cid}/status', json={"status": "CANCELLED"})
        assert res.status_code == 200
        assert res.get_json()["status"] == "CANCELLED"

    # 5. Check metrics endpoint
    metrics_res = client.get('/metrics')
    assert metrics_res.status_code == 200
    content = metrics_res.data.decode('utf-8')
    assert "cargo_created_total" in content
    assert "cargo_delivered_total" in content
    assert "cargo_cancelled_total" in content
    assert "cargo_status_changed_total" in content

