"""
Kafka client utilities (DRY principle)
Shared Kafka producer and consumer for all components
"""
import json
import logging
import os
from typing import Callable, Dict, List, Optional

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class KafkaClient:
    """
    Shared Kafka client for event streaming
    KISS: Simple interface, handles serialization
    """

    def __init__(self, bootstrap_servers: Optional[str] = None):
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BROKERS", "localhost:9092"
        )
        self._producer = None
        self._consumers = {}

    @property
    def producer(self) -> KafkaProducer:
        """Lazy-load producer (YAGNI: only create when needed)"""
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                # Reliability settings
                acks="all",  # Wait for all replicas
                retries=3,
                max_in_flight_requests_per_connection=1,  # Preserve order
            )
            logger.info(f"Kafka producer connected to {self.bootstrap_servers}")
        return self._producer

    async def publish(
        self, topic: str, value: dict, key: Optional[str] = None
    ) -> None:
        """
        Publish message to Kafka topic
        KISS: Simple async publish with idempotency key
        """
        try:
            future = self.producer.send(topic, key=key, value=value)
            # Block until message is sent (or timeout)
            record_metadata = future.get(timeout=10)
            logger.debug(
                f"Published to {topic}: partition={record_metadata.partition}, "
                f"offset={record_metadata.offset}"
            )
        except KafkaError as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            raise

    def create_consumer(
        self, topics: List[str], group_id: str, auto_offset_reset: str = "earliest"
    ) -> KafkaConsumer:
        """
        Create Kafka consumer for topics
        DRY: Reusable consumer factory
        """
        consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id,
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        logger.info(
            f"Created consumer for {topics} with group_id={group_id}"
        )
        return consumer

    async def consume(
        self,
        topics: List[str],
        group_id: str,
        handler: Callable[[str, dict], None],
    ):
        """
        Consume messages from topics and process with handler
        KISS: Simple consume loop
        """
        consumer = self.create_consumer(topics, group_id)
        try:
            logger.info(f"Starting consumer for topics: {topics}")
            for message in consumer:
                try:
                    # Extract event type from topic name
                    event_type = message.topic.split(".")[-1]
                    # Call handler with event type and data
                    await handler(event_type, message.value)
                except Exception as e:
                    logger.error(f"Error processing message from {message.topic}: {e}")
                    # Continue processing other messages
                    continue
        finally:
            consumer.close()
            logger.info(f"Consumer closed for topics: {topics}")

    def close(self):
        """Close all Kafka connections"""
        if self._producer:
            self._producer.close()
            logger.info("Kafka producer closed")


# Singleton instance (DRY: shared across application)
kafka_client = KafkaClient()
