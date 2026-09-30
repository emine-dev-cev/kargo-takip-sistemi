import logging
from flask import Flask, jsonify
from config import Config
from app.models import init_db
from app.kafka_producer import kafka_producer
from app.metrics import setup_metrics
from app.routes import cargo_bp

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s'
)
logger = logging.getLogger(__name__)

def create_app(config_override: dict = None) -> Flask:
    """Application factory for Flask app."""
    app = Flask(__name__)
    
    # Load default config
    app.config.from_object(Config)

    # Apply overrides (for tests / custom envs)
    if config_override:
        app.config.update(config_override)

    # Initialize SQLite database
    db_path = app.config.get('DATABASE_PATH')
    init_db(db_path)
    logger.info(f"Initialized SQLite database at {db_path}")

    # Initialize Kafka Producer
    if not app.config.get('TESTING', False):
        kafka_servers = app.config.get('KAFKA_BOOTSTRAP_SERVERS')
        kafka_topic = app.config.get('KAFKA_TOPIC')
        kafka_producer.init_producer(bootstrap_servers=kafka_servers, topic=kafka_topic)

    # Setup Prometheus metrics
    setup_metrics(app)

    # Sync initial metric counts with SQLite DB state on startup
    try:
        from app.metrics import sync_metrics_with_db
        sync_metrics_with_db(db_path)
    except Exception as e:
        logger.warning(f"Could not sync metrics with DB: {e}")

    # Register blueprints
    app.register_blueprint(cargo_bp)

    @app.route('/', methods=['GET'])
    def root():
        from flask import render_template, request
        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                "service": "Cargo Tracking System API",
                "status": "running",
                "version": "1.0.0"
            }), 200
        return render_template('index.html')

    return app
