"""
FastAPI server for Pepper
KISS: Simple REST API for UI and external integrations
"""
import logging
import os
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from kafka.producers import UserMessageProducer, EmailProducer, ReminderProducer
from kafka.client import kafka_client

logger = logging.getLogger(__name__)

app = FastAPI(title="Pepper API", version="1.0.0")

# Enable CORS for UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize producers
user_message_producer = UserMessageProducer()
email_producer = EmailProducer()
reminder_producer = ReminderProducer()


# Request models
class UserMessage(BaseModel):
    content: str
    user_id: str = "default"


class EmailEvent(BaseModel):
    message_id: str
    from_address: str
    subject: str
    preview: str
    body: str


class ReminderEvent(BaseModel):
    reminder_id: str
    message: str
    reminder_time: str


# Endpoints
@app.post("/api/messages")
async def send_user_message(message: UserMessage):
    """
    Send user message to scheduler
    """
    try:
        await user_message_producer.publish_user_message(
            message.content, message.user_id
        )
        return {"status": "ok", "message": "Message sent"}
    except Exception as e:
        logger.error(f"Error sending user message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/emails")
async def publish_email(email: EmailEvent):
    """
    Publish email event (webhook from email service)
    """
    try:
        await email_producer.publish_email_event(email.dict())
        return {"status": "ok", "message": "Email event published"}
    except Exception as e:
        logger.error(f"Error publishing email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reminders")
async def publish_reminder(reminder: ReminderEvent):
    """
    Publish reminder event
    """
    try:
        await reminder_producer.publish_reminder(reminder.dict())
        return {"status": "ok", "message": "Reminder published"}
    except Exception as e:
        logger.error(f"Error publishing reminder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy"}


@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on shutdown
    """
    kafka_client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
