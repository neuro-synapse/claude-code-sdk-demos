"""
DBOS state management (DRY principle)
Durable state operations for agents
"""
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict

from dbos import step
import asyncpg

logger = logging.getLogger(__name__)


class StateManager:
    """
    Durable state management using DBOS steps
    KISS: Simple save/load operations
    DRY: Reusable across agents
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool

    @step()
    async def save_conversation(
        self, agent_id: str, messages: List[Dict], summary: Optional[str] = None
    ) -> int:
        """
        Save conversation state (DBOS ensures durability)
        Returns: conversation_id
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO conversations (agent_id, messages, summary, created_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                agent_id,
                json.dumps(messages),
                summary,
                datetime.utcnow(),
            )
            logger.debug(f"Saved conversation for agent {agent_id}: id={row['id']}")
            return row["id"]

    @step()
    async def load_conversation(
        self, agent_id: str, limit: int = 1
    ) -> Optional[Dict]:
        """
        Load latest conversation state
        Returns: {id, messages, summary, created_at}
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, messages, summary, created_at
                FROM conversations
                WHERE agent_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                agent_id,
                limit,
            )
            if row:
                return {
                    "id": row["id"],
                    "messages": json.loads(row["messages"]),
                    "summary": row["summary"],
                    "created_at": row["created_at"],
                }
            return None

    @step()
    async def save_user_profile(self, user_id: str, profile_data: Dict) -> None:
        """
        Save or update user profile
        """
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_profiles (user_id, profile_data, updated_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id)
                DO UPDATE SET profile_data = $2, updated_at = $3
                """,
                user_id,
                json.dumps(profile_data),
                datetime.utcnow(),
            )
            logger.debug(f"Saved user profile for {user_id}")

    @step()
    async def load_user_profile(self, user_id: str) -> Optional[Dict]:
        """
        Load user profile
        Returns: profile_data dict or None
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT profile_data FROM user_profiles WHERE user_id = $1",
                user_id,
            )
            if row:
                return json.loads(row["profile_data"])
            return None

    @step()
    async def create_task(
        self, task_id: str, task_type: str, task_data: Dict
    ) -> None:
        """
        Create task assignment
        """
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tasks (task_id, task_type, task_data, status, created_at)
                VALUES ($1, $2, $3, 'pending', $4)
                """,
                task_id,
                task_type,
                json.dumps(task_data),
                datetime.utcnow(),
            )
            logger.debug(f"Created task {task_id} of type {task_type}")

    @step()
    async def update_task_status(
        self, task_id: str, status: str, result: Optional[str] = None
    ) -> None:
        """
        Update task status and result
        """
        async with self.db.acquire() as conn:
            if status == "completed":
                await conn.execute(
                    """
                    UPDATE tasks
                    SET status = $1, completed_at = $2
                    WHERE task_id = $3
                    """,
                    status,
                    datetime.utcnow(),
                    task_id,
                )
            else:
                await conn.execute(
                    "UPDATE tasks SET status = $1 WHERE task_id = $2",
                    status,
                    task_id,
                )
            logger.debug(f"Updated task {task_id} status to {status}")

    @step()
    async def get_task(self, task_id: str) -> Optional[Dict]:
        """
        Get task by ID
        Returns: task dict or None
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT task_id, task_type, task_data, status, created_at, completed_at
                FROM tasks
                WHERE task_id = $1
                """,
                task_id,
            )
            if row:
                return {
                    "task_id": row["task_id"],
                    "task_type": row["task_type"],
                    "task_data": json.loads(row["task_data"]),
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                }
            return None
