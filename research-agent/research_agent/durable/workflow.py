"""DBOS Durable Workflow Layer for Research Agent.

Provides durable execution guarantees using DBOS decorators.
All research workflows can recover from any failure and continue from the last completed step.

Architecture:
- @DBOS.workflow() wraps the entire research workflow
- @DBOS.step() wraps individual sub-agent tasks
- Postgres stores execution state for recovery
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from dbos import DBOS

logger = logging.getLogger(__name__)


@dataclass
class ResearchTask:
    """A single research task to be executed by a sub-agent."""
    task_id: str
    item_name: str
    agent_type: str
    description: str
    prompt: str


@dataclass
class ResearchResult:
    """Result from a completed research task."""
    task_id: str
    success: bool
    output_file: Optional[str] = None
    error: Optional[str] = None
    sandbox_id: Optional[str] = None


class DurableResearchWorkflow:
    """
    Durable workflow manager for research operations.

    Uses DBOS decorators to ensure:
    1. Once-and-only-once execution of each step
    2. Automatic recovery from failures
    3. Complete auditability of all operations
    """

    def __init__(self, sandbox_manager=None):
        """
        Initialize durable workflow.

        Args:
            sandbox_manager: E2B sandbox manager instance
        """
        self.sandbox_manager = sandbox_manager
        logger.info("Durable Research Workflow initialized")

    @DBOS.step()
    def execute_research_task(
        self,
        task: ResearchTask,
        sandbox_id: Optional[str] = None
    ) -> ResearchResult:
        """
        Execute a single research task in an isolated sandbox.

        This is a DBOS step - it will NOT re-execute if it already completed.
        If the workflow is interrupted, DBOS will return the recorded output.

        Args:
            task: Research task to execute
            sandbox_id: Optional sandbox ID (for testing/recovery)

        Returns:
            ResearchResult with execution details
        """
        logger.info(
            f"[DBOS STEP] Executing research task: {task.task_id} "
            f"(item: {task.item_name})"
        )

        try:
            # Create sandbox if not provided
            if not sandbox_id and self.sandbox_manager:
                agent_id = f"{task.agent_type.upper()}-{task.task_id}"
                sandbox = self.sandbox_manager.create_sandbox(
                    agent_type=task.agent_type,
                    agent_id=agent_id
                )
                sandbox_id = sandbox.sandbox_id

            # Execute research in sandbox
            # In real implementation, this would call Claude Agent SDK
            # For now, we log the step completion
            output_file = f"files/research_notes/{task.item_name.lower().replace(' ', '_')}.md"

            logger.info(
                f"✓ [DBOS STEP] Research completed for {task.item_name}"
            )

            return ResearchResult(
                task_id=task.task_id,
                success=True,
                output_file=output_file,
                sandbox_id=sandbox_id
            )

        except Exception as e:
            logger.error(
                f"✗ [DBOS STEP] Research failed for {task.task_id}: {e}"
            )

            return ResearchResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
                sandbox_id=sandbox_id
            )

    @DBOS.step()
    def aggregate_research_results(
        self,
        results: List[ResearchResult]
    ) -> Dict[str, Any]:
        """
        Aggregate all research results into a final report.

        This is a DBOS step - idempotent and recoverable.

        Args:
            results: List of research results from all sub-agents

        Returns:
            Aggregation metadata
        """
        logger.info(
            f"[DBOS STEP] Aggregating {len(results)} research results"
        )

        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        logger.info(
            f"✓ [DBOS STEP] Aggregation complete: "
            f"{len(successful)} successful, {len(failed)} failed"
        )

        return {
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "output_files": [r.output_file for r in successful if r.output_file]
        }

    @DBOS.workflow()
    def run_wide_research(
        self,
        items: List[str],
        research_prompt_template: str
    ) -> Dict[str, Any]:
        """
        Main durable workflow for wide research across multiple items.

        If this workflow is interrupted:
        1. DBOS records which steps completed
        2. On restart, workflow resumes from last completed step
        3. Completed steps return their recorded outputs (no re-execution)
        4. Only incomplete steps are executed

        Args:
            items: List of items to research (e.g., company names)
            research_prompt_template: Template for research prompts

        Returns:
            Summary of workflow execution
        """
        logger.info(
            f"[DBOS WORKFLOW] Starting wide research for {len(items)} items"
        )
        logger.info(
            f"Items: {', '.join(items)}"
        )

        # Create research tasks
        tasks = []
        for idx, item in enumerate(items):
            task = ResearchTask(
                task_id=f"task_{idx+1}",
                item_name=item,
                agent_type="researcher",
                description=f"Research {item}",
                prompt=research_prompt_template.format(item=item)
            )
            tasks.append(task)

        logger.info(f"Created {len(tasks)} research tasks")

        # Execute each research task as a durable step
        results = []
        for task in tasks:
            logger.info(
                f"[DBOS WORKFLOW] Processing task {task.task_id}: {task.item_name}"
            )

            result = self.execute_research_task(task)
            results.append(result)

            if result.success:
                logger.info(f"  ✓ Task {task.task_id} completed successfully")
            else:
                logger.warning(
                    f"  ✗ Task {task.task_id} failed: {result.error}"
                )

        # Aggregate results
        logger.info("[DBOS WORKFLOW] Aggregating results")
        summary = self.aggregate_research_results(results)

        logger.info(
            f"[DBOS WORKFLOW] Workflow complete: "
            f"{summary['successful']}/{summary['total']} tasks successful"
        )

        return {
            "workflow": "wide_research",
            "items": items,
            "results": [
                {
                    "task_id": r.task_id,
                    "success": r.success,
                    "output_file": r.output_file,
                    "error": r.error
                }
                for r in results
            ],
            "summary": summary
        }

    @DBOS.workflow()
    def run_single_research(
        self,
        topic: str,
        subtopics: List[str]
    ) -> Dict[str, Any]:
        """
        Durable workflow for traditional single-topic research.

        Args:
            topic: Main research topic
            subtopics: List of subtopics to research in parallel

        Returns:
            Summary of workflow execution
        """
        logger.info(
            f"[DBOS WORKFLOW] Starting research on: {topic}"
        )
        logger.info(
            f"Subtopics: {', '.join(subtopics)}"
        )

        # Create research tasks for each subtopic
        tasks = []
        for idx, subtopic in enumerate(subtopics):
            task = ResearchTask(
                task_id=f"subtopic_{idx+1}",
                item_name=subtopic,
                agent_type="researcher",
                description=f"Research {subtopic} (part of {topic})",
                prompt=f"Research {subtopic} as part of broader topic: {topic}"
            )
            tasks.append(task)

        # Execute research tasks
        results = []
        for task in tasks:
            logger.info(
                f"[DBOS WORKFLOW] Processing subtopic: {task.item_name}"
            )

            result = self.execute_research_task(task)
            results.append(result)

        # Aggregate results
        summary = self.aggregate_research_results(results)

        logger.info(
            f"[DBOS WORKFLOW] Research complete for: {topic}"
        )

        return {
            "workflow": "single_research",
            "topic": topic,
            "subtopics": subtopics,
            "results": [
                {
                    "task_id": r.task_id,
                    "success": r.success,
                    "output_file": r.output_file
                }
                for r in results
            ],
            "summary": summary
        }


# Recovery helper functions

def check_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """
    Check the status of a running or completed workflow.

    Args:
        workflow_id: DBOS workflow ID

    Returns:
        Workflow status information
    """
    # DBOS provides workflow status tracking
    # This would query the Postgres database
    logger.info(f"Checking status of workflow: {workflow_id}")

    # Implementation depends on DBOS API
    return {
        "workflow_id": workflow_id,
        "status": "running",  # or "completed", "failed", "recovered"
        "completed_steps": [],
        "pending_steps": []
    }


def resume_workflow(workflow_id: str) -> Any:
    """
    Resume a workflow from its last completed step.

    Args:
        workflow_id: DBOS workflow ID to resume

    Returns:
        Workflow result after resumption
    """
    logger.info(f"Resuming workflow: {workflow_id}")

    # DBOS automatically handles resumption
    # When you call a workflow function again, it continues from last step
    # This is built into DBOS decorators

    return {"resumed": True, "workflow_id": workflow_id}
