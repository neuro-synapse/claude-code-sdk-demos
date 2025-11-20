"""
SchedulerAgent: Main orchestrator using Claude Agent SDK + DBOS
Receives events, decides actions, delegates tasks
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from anthropic import Anthropic
from dbos import DBOS, workflow, step
from tzlocal import get_localzone_name

from kafka.client import kafka_client
from dbos.state import StateManager

logger = logging.getLogger(__name__)

# KISS: Simple system prompt (can be externalized later if needed)
SCHEDULER_SYSTEM_PROMPT = """You are an AI scheduling assistant that helps users manage their emails, tasks, and reminders.

Your role:
1. Process incoming events (emails, user messages, reminders)
2. Decide what actions to take
3. Delegate complex tasks to worker agents
4. Respond to users with helpful summaries

Available tools:
- delegate_to_worker: Assign a task to a worker agent
- send_to_user: Send a message to the user
- set_reminder: Create a reminder for later
- wait: No action needed right now

Keep responses concise and actionable.
"""


class SchedulerAgent:
    """
    Main orchestrator agent (Claude SDK + DBOS)
    KISS: Simple event processing workflow
    """

    def __init__(self, state_manager: StateManager):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.state_manager = state_manager
        self.model = "claude-sonnet-4-5-20250929"
        self.max_batch_size = 4  # Process up to 4 events at once

        # Define tools (KISS: only essential tools)
        self.tools = [
            {
                "name": "delegate_to_worker",
                "description": "Delegate a complex task to a worker agent for execution",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "task_description": {
                            "type": "string",
                            "description": "Clear description of the task to be executed",
                        },
                        "task_type": {
                            "type": "string",
                            "description": "Type of task (e.g., 'email_summary', 'research', 'compose_email')",
                        },
                    },
                    "required": ["task_description", "task_type"],
                },
            },
            {
                "name": "send_to_user",
                "description": "Send a message to the user",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Message to display to the user",
                        }
                    },
                    "required": ["message"],
                },
            },
            {
                "name": "wait",
                "description": "No action needed right now",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Optional reason for waiting",
                        }
                    },
                },
            },
        ]

    @workflow()
    async def process_event(self, event_type: str, event_data: Dict) -> Dict:
        """
        DBOS durable workflow: Process an event
        Survives crashes and retries automatically
        """
        agent_id = "scheduler"

        # Step 1: Load context (DBOS step - automatic retry)
        conversation = await self.state_manager.load_conversation(agent_id)
        messages = conversation["messages"] if conversation else []
        summary = conversation.get("summary") if conversation else None

        # Step 2: Build event message
        event_message = self._format_event(event_type, event_data)

        # Step 3: Get timezone info
        tz_name = get_localzone_name()
        local_tz = ZoneInfo(tz_name)
        now_in_zone = datetime.now(local_tz)
        time_str = now_in_zone.strftime("%Y-%m-%d %H:%M:%S")

        # Append new event to messages
        user_content = f"{event_message}\n\nCurrent time: {time_str} at {tz_name}"
        messages.append({"role": "user", "content": user_content})

        # Step 4: Call Claude Agent SDK
        response = await self._call_claude(messages, summary)

        # Step 5: Process response and execute actions
        result = await self._execute_actions(response, messages)

        # Step 6: Save conversation state (DBOS step)
        await self.state_manager.save_conversation(agent_id, messages)

        logger.info(f"Processed {event_type} event: {result}")
        return result

    async def _call_claude(
        self, messages: List[Dict], summary: Optional[str] = None
    ) -> Dict:
        """
        Call Claude Agent SDK
        KISS: Simple messages API call with tools
        """
        # Build system prompt with summary if available
        system_prompt = SCHEDULER_SYSTEM_PROMPT
        if summary:
            system_prompt += f"\n\nPrevious conversation summary:\n{summary}"

        # Call Claude
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=system_prompt,
            messages=messages,
            tools=self.tools,
        )

        # Convert to dict for easier handling
        return {
            "content": [
                {
                    "type": block.type,
                    "text": getattr(block, "text", None),
                    "id": getattr(block, "id", None),
                    "name": getattr(block, "name", None),
                    "input": getattr(block, "input", None),
                }
                for block in response.content
            ],
            "stop_reason": response.stop_reason,
        }

    @step()
    async def _execute_actions(
        self, response: Dict, messages: List[Dict]
    ) -> Dict:
        """
        Execute tool calls from Claude response
        DBOS step: Idempotent execution
        """
        result = {"actions": [], "user_message": None}

        # Add assistant response to conversation
        assistant_message = {"role": "assistant", "content": response["content"]}
        messages.append(assistant_message)

        # Process tool uses
        for block in response["content"]:
            if block["type"] == "tool_use":
                tool_name = block["name"]
                tool_input = block["input"]

                if tool_name == "delegate_to_worker":
                    # Create task and publish to Kafka
                    task_id = str(uuid.uuid4())
                    task_data = {
                        "task_id": task_id,
                        "task_type": tool_input["task_type"],
                        "description": tool_input["task_description"],
                        "created_at": datetime.utcnow().isoformat(),
                    }

                    # Save task to DB
                    await self.state_manager.create_task(
                        task_id, tool_input["task_type"], task_data
                    )

                    # Publish to Kafka
                    await kafka_client.publish(
                        topic="pepper.tasks.assigned", key=task_id, value=task_data
                    )

                    result["actions"].append(
                        {
                            "type": "task_delegated",
                            "task_id": task_id,
                            "task_type": tool_input["task_type"],
                        }
                    )

                elif tool_name == "send_to_user":
                    # Publish to UI topic
                    message = tool_input["message"]
                    await kafka_client.publish(
                        topic="pepper.ui.messages",
                        value={"message": message, "timestamp": datetime.utcnow().isoformat()},
                    )
                    result["user_message"] = message
                    result["actions"].append({"type": "message_sent", "message": message})

                elif tool_name == "wait":
                    result["actions"].append(
                        {"type": "wait", "reason": tool_input.get("reason", "")}
                    )

        return result

    def _format_event(self, event_type: str, event_data: Dict) -> str:
        """
        Format event data into readable message
        KISS: Simple formatting
        """
        if event_type == "email":
            return f"""New email received:
From: {event_data.get('from', 'Unknown')}
Subject: {event_data.get('subject', 'No subject')}
Preview: {event_data.get('preview', '')}"""
        elif event_type == "user":
            return f"User message: {event_data.get('content', '')}"
        elif event_type == "reminder":
            return f"Reminder: {event_data.get('message', '')}"
        else:
            return f"Event ({event_type}): {json.dumps(event_data)}"


async def start_scheduler():
    """
    Start scheduler consumer (listens to event topics)
    KISS: Simple Kafka consumer loop
    """
    import asyncpg
    from dbos.state import StateManager

    # Initialize DB pool
    db_pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "pepper"),
    )

    state_manager = StateManager(db_pool)
    agent = SchedulerAgent(state_manager)

    # Event handler
    async def handle_event(event_type: str, event_data: Dict):
        await agent.process_event(event_type, event_data)

    # Consume from event topics
    await kafka_client.consume(
        topics=[
            "pepper.events.email",
            "pepper.events.user",
            "pepper.events.reminder",
        ],
        group_id="scheduler-group",
        handler=handle_event,
    )


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_scheduler())
