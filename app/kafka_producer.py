import json
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)

class AppKafkaProducer:
    def __init__(self, bootstrap_servers: str = None, topic: str = "cargo-events"):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = None
        self._initialized = False

    def init_producer(self, bootstrap_servers: str = None, topic: str = None):
        """Initializes or reconfigures the Kafka Producer."""
        if bootstrap_servers:
            self.bootstrap_servers = bootstrap_servers
        if topic:
            self.topic = topic

        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3,
                request_timeout_ms=5000
            )
            self._initialized = True
            logger.info(f"Connected to Kafka broker at {self.bootstrap_servers}")
        except Exception as e:
            self.producer = None
            self._initialized = False
            logger.warning(f"Kafka broker not available at {self.bootstrap_servers}: {e}")

    def send_event(self, event_data: dict, topic: str = None) -> bool:
        """Sends an event payload to Kafka topic."""
        target_topic = topic or self.topic
        
        # Try reconnecting if not initialized
        if not self._initialized or self.producer is None:
            if self.bootstrap_servers:
                self.init_producer(self.bootstrap_servers, self.topic)

        if not self._initialized or self.producer is None:
            logger.warning(f"Skipping event send (Kafka not connected): {event_data}")
            return False

        try:
            future = self.producer.send(target_topic, value=event_data)
            self.producer.flush()
            record_metadata = future.get(timeout=5)
            logger.info(f"Event sent to {record_metadata.topic} partition {record_metadata.partition} offset {record_metadata.offset}: {event_data}")
            return True
        except KafkaError as e:
            logger.error(f"Failed to send Kafka event: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Kafka event: {e}")
            return False

    def send_cargo_created(self, cargo_id: int, tracking_number: str):
        """Dispatches cargo.created event."""
        payload = {
            "event": "cargo.created",
            "cargo_id": cargo_id,
            "tracking_number": tracking_number
        }
        return self.send_event(payload)

    def send_cargo_status_changed(self, cargo_id: int, status: str):
        """Dispatches cargo.status_changed event."""
        payload = {
            "event": "cargo.status_changed",
            "cargo_id": cargo_id,
            "status": status
        }
        return self.send_event(payload)

    def send_cargo_delivered(self, cargo_id: int):
        """Dispatches cargo.delivered event."""
        payload = {
            "event": "cargo.delivered",
            "cargo_id": cargo_id
        }
        return self.send_event(payload)

    def send_cargo_cancelled(self, cargo_id: int):
        """Dispatches cargo.cancelled event."""
        payload = {
            "event": "cargo.cancelled",
            "cargo_id": cargo_id
        }
        return self.send_event(payload)

kafka_producer = AppKafkaProducer()
