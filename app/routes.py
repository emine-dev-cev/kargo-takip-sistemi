import logging
from flask import Blueprint, request, jsonify, current_app
from app.models import (
    create_cargo,
    get_cargo_by_id,
    get_all_cargos,
    update_cargo_status,
    delete_cargo,
    VALID_STATUSES
)
from app.metrics import (
    cargo_created_total,
    cargo_delivered_total,
    cargo_cancelled_total,
    cargo_status_changed_total,
    sync_metrics_with_db
)
from app.kafka_producer import kafka_producer

logger = logging.getLogger(__name__)

cargo_bp = Blueprint('cargo', __name__)

@cargo_bp.route('/cargo', methods=['POST'])
def handle_create_cargo():
    """Creates a new cargo item."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON request body"}), 400

    tracking_number = data.get('tracking_number')
    sender = data.get('sender')
    receiver = data.get('receiver')

    if not tracking_number or not str(tracking_number).strip():
        return jsonify({"error": "tracking_number is required and cannot be empty"}), 400

    if not sender or not str(sender).strip():
        return jsonify({"error": "sender is required and cannot be empty"}), 400

    if not receiver or not str(receiver).strip():
        return jsonify({"error": "receiver is required and cannot be empty"}), 400

    db_path = current_app.config.get('DATABASE_PATH')
    try:
        cargo = create_cargo(tracking_number, sender, receiver, db_path)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Increment metric & sync with DB
    sync_metrics_with_db(db_path)

    # Emit Kafka event
    kafka_producer.send_cargo_created(cargo['id'], cargo['tracking_number'])

    return jsonify(cargo), 201


@cargo_bp.route('/cargo/<int:cargo_id>', methods=['GET'])
def handle_get_cargo(cargo_id: int):
    """Retrieves a single cargo by ID."""
    db_path = current_app.config.get('DATABASE_PATH')
    cargo = get_cargo_by_id(cargo_id, db_path)
    if not cargo:
        return jsonify({"error": "Cargo not found"}), 404

    return jsonify(cargo), 200


@cargo_bp.route('/cargo', methods=['GET'])
def handle_get_all_cargos():
    """Retrieves all cargos."""
    db_path = current_app.config.get('DATABASE_PATH')
    cargos = get_all_cargos(db_path)
    return jsonify(cargos), 200


@cargo_bp.route('/cargo/<int:cargo_id>/status', methods=['PUT'])
def handle_update_cargo_status(cargo_id: int):
    """Updates status for an existing cargo."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON request body"}), 400

    new_status = data.get('status')
    if not new_status or new_status not in VALID_STATUSES:
        return jsonify({
            "error": f"Invalid status: '{new_status}'. Valid statuses: {', '.join(sorted(VALID_STATUSES))}"
        }), 400

    db_path = current_app.config.get('DATABASE_PATH')
    
    # Check existence
    existing_cargo = get_cargo_by_id(cargo_id, db_path)
    if not existing_cargo:
        return jsonify({"error": "Cargo not found"}), 404

    try:
        updated_cargo = update_cargo_status(cargo_id, new_status, db_path)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Increment status change metric & sync with DB
    cargo_status_changed_total.inc()
    kafka_producer.send_cargo_status_changed(cargo_id, new_status)

    if new_status == "DELIVERED":
        kafka_producer.send_cargo_delivered(cargo_id)
    elif new_status == "CANCELLED":
        kafka_producer.send_cargo_cancelled(cargo_id)

    sync_metrics_with_db(db_path)

    return jsonify(updated_cargo), 200


@cargo_bp.route('/cargo/<int:cargo_id>', methods=['DELETE'])
def handle_delete_cargo(cargo_id: int):
    """Deletes a cargo by ID."""
    db_path = current_app.config.get('DATABASE_PATH')
    deleted = delete_cargo(cargo_id, db_path)
    if not deleted:
        return jsonify({"error": "Cargo not found"}), 404

    sync_metrics_with_db(db_path)
    return jsonify({"message": "Cargo deleted successfully"}), 200


@cargo_bp.route('/reset', methods=['POST'])
def handle_reset_system():
    """Resets the SQLite database and restarts counts for clean testing."""
    import sqlite3
    db_path = current_app.config.get('DATABASE_PATH')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cargo")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='cargo'")
    conn.commit()
    conn.close()

    cargo_created_total.set(0)
    cargo_delivered_total.set(0)
    cargo_cancelled_total.set(0)
    cargo_status_changed_total.set(0)
    return jsonify({"message": "Database reset successfully"}), 200

