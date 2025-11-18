"""E2B Sandbox Manager for isolated sub-agent execution.

Simple, focused manager that creates and manages E2B sandboxes for each sub-agent.
Each sandbox provides:
- Isolated execution environment (Firecracker microVM)
- Full tool library access
- Independent internet connection
- Fresh context window
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from e2b_code_interpreter import Sandbox

logger = logging.getLogger(__name__)


@dataclass
class SandboxInfo:
    """Information about an active sandbox."""
    sandbox_id: str
    agent_type: str
    agent_id: str
    sandbox: Sandbox
    created_at: str


class E2BSandboxManager:
    """
    Manages E2B sandboxes for sub-agent execution.

    Follows KISS principle: simple create, execute, cleanup cycle.
    Each sub-agent gets its own isolated sandbox.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the sandbox manager.

        Args:
            api_key: E2B API key (optional, can use E2B_API_KEY env var)
        """
        self.api_key = api_key
        self.active_sandboxes: Dict[str, SandboxInfo] = {}
        logger.info("E2B Sandbox Manager initialized")

    def create_sandbox(self, agent_type: str, agent_id: str) -> Sandbox:
        """
        Create a new isolated sandbox for a sub-agent.

        Args:
            agent_type: Type of agent (e.g., 'researcher', 'report-writer')
            agent_id: Unique identifier (e.g., 'RESEARCHER-1')

        Returns:
            Sandbox instance ready for code execution
        """
        from datetime import datetime

        logger.info(f"Creating E2B sandbox for {agent_id} (type: {agent_type})")

        try:
            # Create sandbox (inherits API key from env if not provided)
            sandbox = Sandbox.create()

            sandbox_info = SandboxInfo(
                sandbox_id=sandbox.sandbox_id,
                agent_type=agent_type,
                agent_id=agent_id,
                sandbox=sandbox,
                created_at=datetime.now().isoformat()
            )

            self.active_sandboxes[agent_id] = sandbox_info

            logger.info(
                f"✓ Sandbox created for {agent_id}: {sandbox.sandbox_id} "
                f"(startup ~150ms)"
            )

            return sandbox

        except Exception as e:
            logger.error(f"Failed to create sandbox for {agent_id}: {e}")
            raise

    def execute_code(
        self,
        agent_id: str,
        code: str,
        timeout: Optional[int] = 300
    ) -> Dict[str, Any]:
        """
        Execute code in an agent's sandbox.

        Args:
            agent_id: Agent identifier
            code: Python code to execute
            timeout: Execution timeout in seconds (default: 5 minutes)

        Returns:
            Execution result with stdout, stderr, and status
        """
        if agent_id not in self.active_sandboxes:
            raise ValueError(f"No active sandbox for agent {agent_id}")

        sandbox_info = self.active_sandboxes[agent_id]
        sandbox = sandbox_info.sandbox

        logger.debug(f"Executing code in sandbox for {agent_id}")

        try:
            execution = sandbox.run_code(code, timeout=timeout)

            result = {
                "success": not execution.error,
                "text": execution.text,
                "stdout": execution.logs.stdout,
                "stderr": execution.logs.stderr,
                "error": execution.error.value if execution.error else None,
                "results": execution.results
            }

            if execution.error:
                logger.warning(
                    f"Code execution error in {agent_id}: {execution.error.value}"
                )
            else:
                logger.debug(f"Code executed successfully in {agent_id}")

            return result

        except Exception as e:
            logger.error(f"Sandbox execution failed for {agent_id}: {e}")
            return {
                "success": False,
                "text": "",
                "stdout": "",
                "stderr": str(e),
                "error": str(e),
                "results": []
            }

    def install_package(self, agent_id: str, package: str) -> bool:
        """
        Install a Python package in an agent's sandbox.

        Args:
            agent_id: Agent identifier
            package: Package name (e.g., 'requests', 'beautifulsoup4')

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Installing {package} in sandbox for {agent_id}")

        code = f"import subprocess; subprocess.run(['pip', 'install', '{package}'], check=True)"
        result = self.execute_code(agent_id, code)

        if result["success"]:
            logger.info(f"✓ Installed {package} in {agent_id}")
        else:
            logger.error(f"✗ Failed to install {package} in {agent_id}")

        return result["success"]

    def write_file(
        self,
        agent_id: str,
        file_path: str,
        content: str
    ) -> bool:
        """
        Write a file in an agent's sandbox.

        Args:
            agent_id: Agent identifier
            file_path: Path within sandbox
            content: File content

        Returns:
            True if successful, False otherwise
        """
        if agent_id not in self.active_sandboxes:
            raise ValueError(f"No active sandbox for agent {agent_id}")

        sandbox_info = self.active_sandboxes[agent_id]
        sandbox = sandbox_info.sandbox

        logger.debug(f"Writing file {file_path} in sandbox for {agent_id}")

        try:
            sandbox.files.write(file_path, content)
            logger.debug(f"✓ File written: {file_path} in {agent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to write file {file_path} in {agent_id}: {e}")
            return False

    def read_file(self, agent_id: str, file_path: str) -> Optional[str]:
        """
        Read a file from an agent's sandbox.

        Args:
            agent_id: Agent identifier
            file_path: Path within sandbox

        Returns:
            File content, or None if failed
        """
        if agent_id not in self.active_sandboxes:
            raise ValueError(f"No active sandbox for agent {agent_id}")

        sandbox_info = self.active_sandboxes[agent_id]
        sandbox = sandbox_info.sandbox

        logger.debug(f"Reading file {file_path} from sandbox for {agent_id}")

        try:
            content = sandbox.files.read(file_path)
            logger.debug(f"✓ File read: {file_path} from {agent_id}")
            return content

        except Exception as e:
            logger.error(f"Failed to read file {file_path} from {agent_id}: {e}")
            return None

    def close_sandbox(self, agent_id: str):
        """
        Close and cleanup a specific sandbox.

        Args:
            agent_id: Agent identifier
        """
        if agent_id not in self.active_sandboxes:
            logger.warning(f"No active sandbox to close for {agent_id}")
            return

        sandbox_info = self.active_sandboxes[agent_id]

        try:
            sandbox_info.sandbox.close()
            del self.active_sandboxes[agent_id]
            logger.info(f"✓ Closed sandbox for {agent_id}")

        except Exception as e:
            logger.error(f"Error closing sandbox for {agent_id}: {e}")

    def close_all(self):
        """Close all active sandboxes."""
        logger.info(f"Closing {len(self.active_sandboxes)} active sandboxes")

        for agent_id in list(self.active_sandboxes.keys()):
            self.close_sandbox(agent_id)

        logger.info("All sandboxes closed")

    def get_sandbox_info(self, agent_id: str) -> Optional[SandboxInfo]:
        """
        Get information about an active sandbox.

        Args:
            agent_id: Agent identifier

        Returns:
            SandboxInfo or None if not found
        """
        return self.active_sandboxes.get(agent_id)

    def list_active_sandboxes(self) -> list[str]:
        """
        List all active sandbox agent IDs.

        Returns:
            List of agent IDs with active sandboxes
        """
        return list(self.active_sandboxes.keys())
