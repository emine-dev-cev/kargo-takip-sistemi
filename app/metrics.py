import time
from flask import request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry, REGISTRY

# Define Prometheus metrics
cargo_created_total = Counter(
    'cargo_created_total',
    'Total number of created cargo shipments'
)

cargo_delivered_total = Counter(
    'cargo_delivered_total',
    'Total number of delivered cargo shipments'
)

cargo_cancelled_total = Counter(
    'cargo_cancelled_total',
    'Total number of cancelled cargo shipments'
)

cargo_status_changed_total = Counter(
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
        """Exposes Prometheus metrics endpoint."""
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
