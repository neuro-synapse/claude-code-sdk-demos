"""
Event producers for Pepper
KISS: Simple producers for each event type
"""
import logging
from typing import Dict

from kafka.client import kafka_client

logger = logging.getLogger(__name__)


class EmailProducer:
    """
    Publishes email events to Kafka
    KISS: Simple wrapper around kafka_client
    """

    async def publish_email_event(self, email_data: Dict) -> None:
        """
        Publish email event
        email_data: {from, subject, preview, body, ...}
        """
        await kafka_client.publish(
            topic="pepper.events.email",
            key=email_data.get("message_id"),
            value=email_data,
        )
        logger.info(f"Published email event: {email_data.get('subject')}")


class UserMessageProducer:
    """
    Publishes user messages to Kafka
    """

    async def publish_user_message(self, content: str, user_id: str = "default") -> None:
        """
        Publish user message from UI
        """
        await kafka_client.publish(
            topic="pepper.events.user",
            key=user_id,
            value={"content": content, "user_id": user_id},
        )
        logger.info(f"Published user message from {user_id}")


class ReminderProducer:
    """
    Publishes reminder events to Kafka
    """

    async def publish_reminder(self, reminder_data: Dict) -> None:
        """
        Publish reminder event
        reminder_data: {message, reminder_time, ...}
        """
        await kafka_client.publish(
            topic="pepper.events.reminder",
            key=reminder_data.get("reminder_id"),
            value=reminder_data,
        )
        logger.info(f"Published reminder: {reminder_data.get('message')}")
