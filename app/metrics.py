import time
import logging
from flask import request, Response
from prometheus_client import Gauge, Histogram, Counter, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# Define Prometheus metrics as Gauges so they accurately synchronize with persistent database
cargo_created_total = Gauge(
    'cargo_created_total',
    'Total number of cargo shipments in the system'
)

cargo_delivered_total = Gauge(
    'cargo_delivered_total',
    'Total number of delivered cargo shipments'
)

cargo_cancelled_total = Gauge(
    'cargo_cancelled_total',
    'Total number of cancelled cargo shipments'
)

cargo_status_changed_total = Gauge(
    'cargo_status_changed_total',
    'Total number of cargo status transitions'
)

api_request_total = Counter(
    'api_request_total',
    'Total number of HTTP requests processed by API',
    ['method', 'endpoint', 'status_code']
)

api_request_duration = Histogram(
    'api_request_duration_seconds',
    'Duration of HTTP requests in seconds',
    ['method', 'endpoint']
)

def sync_metrics_with_db(db_path: str):
    """Synchronizes Prometheus metric gauges directly with the SQLite database state."""
    if not db_path:
        return
    try:
        from app.models import get_all_cargos
        cargos = get_all_cargos(db_path)
        total = len(cargos)
        delivered = sum(1 for c in cargos if c.get('status') == 'DELIVERED')
        cancelled = sum(1 for c in cargos if c.get('status') == 'CANCELLED')
        
        cargo_created_total.set(total)
        cargo_delivered_total.set(delivered)
        cargo_cancelled_total.set(cancelled)
    except Exception as e:
        logger.warning(f"Could not sync metrics with DB: {e}")

def setup_metrics(app):
    """Sets up request instrumentation and /metrics route on the Flask app."""

    @app.before_request
    def start_timer():
        request._start_time = time.time()

    @app.after_request
    def record_metrics(response):
        if request.path == '/metrics':
            return response

        if hasattr(request, '_start_time'):
            resp_time = time.time() - request._start_time
            endpoint = request.url_rule.rule if request.url_rule else request.path
            method = request.method
            status_code = str(response.status_code)

            api_request_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
            api_request_duration.labels(method=method, endpoint=endpoint).observe(resp_time)

        return response

    @app.route('/metrics', methods=['GET'])
    def metrics_endpoint():
        """Exposes Prometheus metrics endpoint with live SQLite synchronization."""
        db_path = app.config.get('DATABASE_PATH')
        sync_metrics_with_db(db_path)
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
