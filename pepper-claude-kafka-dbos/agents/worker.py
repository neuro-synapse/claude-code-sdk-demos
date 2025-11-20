"""
WorkerAgent: Task executor using Claude Agent SDK + DBOS
Executes delegated tasks with tool access
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from anthropic import Anthropic
from dbos import DBOS, workflow, step
from tzlocal import get_localzone_name

from kafka.client import kafka_client
from dbos.state import StateManager

logger = logging.getLogger(__name__)

# KISS: Simple worker prompt
WORKER_SYSTEM_PROMPT = """You are a task execution agent. Your role is to complete assigned tasks efficiently.

You have access to tools to help you complete tasks. Execute the task step-by-step and return the final result when done.

When you've completed the task, use the return_result tool with your final answer.
"""


class WorkerAgent:
    """
    Task executor agent (Claude SDK + DBOS)
    KISS: Execute task, return result
    """

    def __init__(self, state_manager: StateManager, worker_id: str = "worker-1"):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.state_manager = state_manager
        self.worker_id = worker_id
        self.model = "claude-sonnet-4-5-20250929"
        self.max_steps = 10  # Max reasoning steps

        # Define tools (YAGNI: start with basics, add more as needed)
        self.tools = [
            {
                "name": "return_result",
                "description": "Return the final result of the task",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "result": {
                            "type": "string",
                            "description": "The final result or answer",
                        }
                    },
                    "required": ["result"],
                },
            },
            # TODO: Add more tools (web search, email compose, etc.)
            # from MCP servers as needed (YAGNI)
        ]

    @workflow()
    async def execute_task(self, task: Dict) -> Dict:
        """
        DBOS durable workflow: Execute a task
        Survives crashes and retries automatically
        """
        task_id = task["task_id"]
        task_type = task["task_type"]
        description = task["description"]

        logger.info(f"Worker {self.worker_id} executing task {task_id}")

        # Step 1: Update task status
        await self.state_manager.update_task_status(task_id, "in_progress")

        # Step 2: Load worker conversation state
        agent_id = f"worker-{self.worker_id}-{task_id}"
        conversation = await self.state_manager.load_conversation(agent_id)
        messages = conversation["messages"] if conversation else []

        # Step 3: Add task description
        tz_name = get_localzone_name()
        local_tz = ZoneInfo(tz_name)
        now_in_zone = datetime.now(local_tz)
        time_str = now_in_zone.strftime("%Y-%m-%d %H:%M:%S")

        task_message = f"""Task: {description}
Task Type: {task_type}
Current time: {time_str} at {tz_name}

Please complete this task and return the result."""

        messages.append({"role": "user", "content": task_message})

        # Step 4: Execute agent loop
        result = await self._agent_loop(messages)

        # Step 5: Save conversation
        await self.state_manager.save_conversation(agent_id, messages)

        # Step 6: Update task status and publish result
        await self.state_manager.update_task_status(task_id, "completed")

        result_data = {
            "task_id": task_id,
            "worker_id": self.worker_id,
            "result": result,
            "completed_at": datetime.utcnow().isoformat(),
        }

        await kafka_client.publish(
            topic="pepper.tasks.results", key=task_id, value=result_data
        )

        logger.info(f"Worker {self.worker_id} completed task {task_id}")
        return result_data

    async def _agent_loop(self, messages: List[Dict]) -> str:
        """
        Claude Agent SDK loop with tool calling
        KISS: Simple agentic loop
        """
        for step in range(self.max_steps):
            # Call Claude
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                system=WORKER_SYSTEM_PROMPT,
                messages=messages,
                tools=self.tools,
            )

            # Add assistant response
            assistant_content = []
            tool_results = []

            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )

                    # Execute tool
                    if block.name == "return_result":
                        # Task complete
                        result = block.input["result"]
                        messages.append(
                            {"role": "assistant", "content": assistant_content}
                        )
                        return result
                    else:
                        # Execute other tools (TODO: implement when needed)
                        tool_result = {"type": "text", "text": "Tool not yet implemented"}
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": tool_result,
                            }
                        )

            # Add assistant message
            messages.append({"role": "assistant", "content": assistant_content})

            # If no tool results, we're done (no more actions)
            if not tool_results:
                # Return last text response
                for block in reversed(assistant_content):
                    if block["type"] == "text":
                        return block["text"]
                return "Task completed"

            # Add tool results
            messages.append({"role": "user", "content": tool_results})

        # Max steps reached
        return "Task incomplete: max steps reached"


async def start_worker(worker_id: str = "worker-1"):
    """
    Start worker consumer (listens to task topic)
    KISS: Simple Kafka consumer loop
    """
    import asyncpg

    # Initialize DB pool
    db_pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "pepper"),
    )

    state_manager = StateManager(db_pool)
    agent = WorkerAgent(state_manager, worker_id)

    # Task handler
    async def handle_task(event_type: str, task_data: Dict):
        await agent.execute_task(task_data)

    # Consume from task topic
    await kafka_client.consume(
        topics=["pepper.tasks.assigned"],
        group_id=f"worker-group",  # Same group = load balancing
        handler=handle_task,
    )


if __name__ == "__main__":
    import asyncio
    import sys

    logging.basicConfig(level=logging.INFO)

    worker_id = sys.argv[1] if len(sys.argv) > 1 else "worker-1"
    asyncio.run(start_worker(worker_id))
