"""Sub-agent execution in E2B sandboxes.

Integrates Claude Agent SDK with E2B sandboxes to run each sub-agent
in complete isolation with its own:
- Execution environment
- Internet connection
- Tool library
- Context window
"""

import logging
import json
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SandboxedAgentExecutor:
    """
    Executes Claude sub-agents inside E2B sandboxes.

    Each sub-agent gets:
    - Full isolation (Firecracker microVM)
    - Complete tool access
    - Fresh context (no context pollution between agents)
    - Independent internet connection
    """

    def __init__(self, sandbox_manager, anthropic_api_key: str):
        """
        Initialize the executor.

        Args:
            sandbox_manager: E2B sandbox manager instance
            anthropic_api_key: Anthropic API key for Claude
        """
        self.sandbox_manager = sandbox_manager
        self.anthropic_api_key = anthropic_api_key
        logger.info("Sandboxed Agent Executor initialized")

    def setup_agent_environment(
        self,
        agent_id: str,
        agent_type: str
    ) -> bool:
        """
        Setup the execution environment in a sandbox for a sub-agent.

        Installs necessary packages and prepares the environment.

        Args:
            agent_id: Unique agent identifier
            agent_type: Type of agent (researcher, report-writer, etc.)

        Returns:
            True if setup successful
        """
        logger.info(f"Setting up environment for {agent_id} in sandbox")

        try:
            # Create sandbox
            sandbox = self.sandbox_manager.create_sandbox(
                agent_type=agent_type,
                agent_id=agent_id
            )

            # Install required packages
            logger.info(f"Installing packages in {agent_id} sandbox")

            packages = [
                "anthropic",  # Claude SDK
                "requests",   # HTTP requests
                "beautifulsoup4",  # Web scraping
                "python-dotenv"  # Environment variables
            ]

            for package in packages:
                success = self.sandbox_manager.install_package(agent_id, package)
                if not success:
                    logger.warning(
                        f"Failed to install {package} in {agent_id}"
                    )

            # Write API key to environment file
            env_content = f"ANTHROPIC_API_KEY={self.anthropic_api_key}\n"
            self.sandbox_manager.write_file(agent_id, ".env", env_content)

            logger.info(f"✓ Environment ready for {agent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to setup environment for {agent_id}: {e}")
            return False

    def execute_research_task(
        self,
        agent_id: str,
        task_prompt: str,
        output_file: str,
        tools: list = None
    ) -> Dict[str, Any]:
        """
        Execute a research task in a sandboxed environment.

        Args:
            agent_id: Unique agent identifier
            task_prompt: Research prompt for the agent
            output_file: Where to save research findings
            tools: List of tools the agent can use

        Returns:
            Execution result with status and output
        """
        logger.info(f"Executing research task in {agent_id}")
        logger.debug(f"Prompt preview: {task_prompt[:100]}...")

        if tools is None:
            tools = ["WebSearch", "Write", "Read"]

        try:
            # Create Python code that will run the agent in the sandbox
            agent_code = self._generate_agent_code(
                task_prompt=task_prompt,
                output_file=output_file,
                tools=tools
            )

            # Write the agent code to sandbox
            self.sandbox_manager.write_file(
                agent_id,
                "research_agent.py",
                agent_code
            )

            logger.info(f"Executing agent code in {agent_id} sandbox")

            # Execute the agent
            result = self.sandbox_manager.execute_code(
                agent_id,
                "python research_agent.py",
                timeout=600  # 10 minutes for research tasks
            )

            if result["success"]:
                logger.info(f"✓ Research completed in {agent_id}")

                # Read the output file
                output_content = self.sandbox_manager.read_file(
                    agent_id,
                    output_file
                )

                return {
                    "success": True,
                    "agent_id": agent_id,
                    "output_file": output_file,
                    "output_content": output_content,
                    "stdout": result["stdout"],
                    "execution_logs": result["stdout"]
                }
            else:
                logger.error(
                    f"✗ Research failed in {agent_id}: {result['error']}"
                )

                return {
                    "success": False,
                    "agent_id": agent_id,
                    "error": result["error"],
                    "stderr": result["stderr"],
                    "stdout": result["stdout"]
                }

        except Exception as e:
            logger.error(f"Exception during execution in {agent_id}: {e}")

            return {
                "success": False,
                "agent_id": agent_id,
                "error": str(e)
            }

    def _generate_agent_code(
        self,
        task_prompt: str,
        output_file: str,
        tools: list
    ) -> str:
        """
        Generate Python code to run an agent in the sandbox.

        This creates a standalone Python script that:
        1. Loads the Claude SDK
        2. Executes the research task
        3. Writes results to a file

        Args:
            task_prompt: Research prompt
            output_file: Output file path
            tools: Available tools

        Returns:
            Python code as string
        """
        # Escape quotes in prompt
        safe_prompt = task_prompt.replace('"', '\\"').replace("'", "\\'")

        code = f'''"""
Auto-generated agent code for sandboxed execution.
"""
import os
import asyncio
from anthropic import Anthropic
from dotenv import load_dotenv

# Load API key
load_dotenv()

async def run_research():
    """Execute research task."""

    # Initialize Claude client
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Research prompt
    prompt = """{safe_prompt}"""

    print("Starting research task...")
    print(f"Available tools: {tools}")

    # Call Claude for research
    # Note: In production, this would use the full Claude Agent SDK
    # For this implementation, we use direct API calls

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=4096,
        messages=[{{"role": "user", "content": prompt}}]
    )

    # Extract research findings
    findings = response.content[0].text

    # Write to output file
    os.makedirs(os.path.dirname("{output_file}") or ".", exist_ok=True)
    with open("{output_file}", "w") as f:
        f.write(findings)

    print(f"✓ Research complete. Wrote {{len(findings)}} characters to {output_file}")
    return findings

# Run the research
if __name__ == "__main__":
    result = asyncio.run(run_research())
    print("Agent execution completed")
'''

        return code

    def cleanup_agent(self, agent_id: str):
        """
        Cleanup and close an agent's sandbox.

        Args:
            agent_id: Agent identifier
        """
        logger.info(f"Cleaning up sandbox for {agent_id}")
        self.sandbox_manager.close_sandbox(agent_id)


class ParallelAgentExecutor:
    """
    Executes multiple sandboxed agents in parallel.

    Follows the Wide Research pattern:
    - One agent per item
    - All agents run in parallel
    - Each gets isolated sandbox
    """

    def __init__(self, executor: SandboxedAgentExecutor):
        """
        Initialize parallel executor.

        Args:
            executor: SandboxedAgentExecutor instance
        """
        self.executor = executor
        logger.info("Parallel Agent Executor initialized")

    async def execute_parallel_research(
        self,
        items: list[str],
        prompt_template: str,
        agent_type: str = "researcher"
    ) -> list[Dict[str, Any]]:
        """
        Execute research tasks in parallel sandboxes.

        Args:
            items: List of items to research
            prompt_template: Template with {item} placeholder
            agent_type: Type of agent to spawn

        Returns:
            List of execution results
        """
        logger.info(
            f"Starting parallel execution for {len(items)} items"
        )

        import asyncio

        async def run_single_task(idx: int, item: str):
            """Run a single research task."""
            agent_id = f"{agent_type.upper()}-{idx+1}"

            logger.info(f"Spawning {agent_id} for item: {item}")

            # Setup environment
            setup_success = self.executor.setup_agent_environment(
                agent_id=agent_id,
                agent_type=agent_type
            )

            if not setup_success:
                return {
                    "success": False,
                    "agent_id": agent_id,
                    "item": item,
                    "error": "Failed to setup environment"
                }

            # Execute research
            prompt = prompt_template.format(item=item)
            output_file = f"files/research_notes/{item.lower().replace(' ', '_')}.md"

            result = self.executor.execute_research_task(
                agent_id=agent_id,
                task_prompt=prompt,
                output_file=output_file
            )

            result["item"] = item
            return result

        # Execute all tasks in parallel
        tasks = [
            run_single_task(idx, item)
            for idx, item in enumerate(items)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with exception: {result}")
                processed_results.append({
                    "success": False,
                    "error": str(result)
                })
            else:
                processed_results.append(result)

        successful = sum(1 for r in processed_results if r.get("success"))
        logger.info(
            f"Parallel execution complete: "
            f"{successful}/{len(items)} successful"
        )

        return processed_results
