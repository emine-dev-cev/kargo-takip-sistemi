import os
import json
import time
import logging
import sys
from kafka import KafkaConsumer
from kafka.errors import KafkaError

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [Consumer]: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'cargo-events')
GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'cargo-consumer-group')

def process_event(event_data: dict):
    """Processes incoming cargo event from Kafka."""
    if not isinstance(event_data, dict):
        logger.warning(f"Received invalid event format: {event_data}")
        return

    event_type = event_data.get('event')
    cargo_id = event_data.get('cargo_id')
    
    if event_type == 'cargo.created':
        tracking_number = event_data.get('tracking_number', 'N/A')
        print(f"[EVENT] New cargo created -> Cargo ID: {cargo_id}, Tracking Number: {tracking_number}", flush=True)
        logger.info(f"Processed cargo.created for Cargo ID {cargo_id} ({tracking_number})")

    elif event_type == 'cargo.status_changed':
        status = event_data.get('status', 'UNKNOWN')
        print(f"[EVENT] Cargo {cargo_id} status changed to {status}", flush=True)
        logger.info(f"Processed cargo.status_changed for Cargo ID {cargo_id} -> {status}")

    elif event_type == 'cargo.delivered':
        # Exact format requested: Cargo <id> delivered.
        print(f"Cargo {cargo_id} delivered.", flush=True)
        logger.info(f"Processed cargo.delivered for Cargo ID {cargo_id}")

    elif event_type == 'cargo.cancelled':
        print(f"[EVENT] Cargo {cargo_id} cancelled.", flush=True)
        logger.info(f"Processed cargo.cancelled for Cargo ID {cargo_id}")

    else:
        print(f"[EVENT] Unknown event received: {event_data}", flush=True)
        logger.warning(f"Unknown event type: {event_type}")

def run_consumer():
    """Main consumer loop with reconnection retry mechanism."""
    logger.info(f"Starting Kafka Consumer for topic '{KAFKA_TOPIC}' on brokers '{KAFKA_BOOTSTRAP_SERVERS}'...")
    
    consumer = None
    retry_delay = 3

    while consumer is None:
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id=GROUP_ID
            )
            logger.info(f"Successfully connected to Kafka topic '{KAFKA_TOPIC}'!")
        except (KafkaError, Exception) as e:
            logger.warning(f"Waiting for Kafka broker to become available ({e}). Retrying in {retry_delay}s...")
            time.sleep(retry_delay)

    print("=" * 60, flush=True)
    print(f"[*] Cargo Events Consumer is active and listening on topic '{KAFKA_TOPIC}'", flush=True)
    print("=" * 60, flush=True)

    try:
        for message in consumer:
            try:
                event_data = message.value
                process_event(event_data)
            except Exception as ex:
                logger.error(f"Error processing message: {ex}")
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user.")
    finally:
        if consumer:
            consumer.close()
            logger.info("Kafka consumer connection closed.")

if __name__ == '__main__':
    run_consumer()
