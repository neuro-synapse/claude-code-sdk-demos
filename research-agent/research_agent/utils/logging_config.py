"""Comprehensive logging configuration for durable research agent.

Provides structured logging across all components:
- E2B sandbox operations
- DBOS workflow steps
- Agent execution
- Error tracking and debugging
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Colored console output for better readability."""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }

    def format(self, record):
        """Format log record with colors."""
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            )

        # Format the message
        formatted = super().format(record)

        # Reset color at the end
        return formatted


def setup_logging(
    session_dir: Optional[Path] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG
) -> Path:
    """
    Setup comprehensive logging configuration.

    Creates:
    1. Colored console output (INFO and above)
    2. Detailed file log (DEBUG and above)
    3. Error-only log file
    4. Structured JSON log for analysis

    Args:
        session_dir: Directory for log files (auto-created if None)
        console_level: Console logging level
        file_level: File logging level

    Returns:
        Path to log directory
    """
    # Create session directory if needed
    if session_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = Path("logs") / f"session_{timestamp}"

    session_dir.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything

    # Remove existing handlers
    root_logger.handlers.clear()

    # 1. Console handler (colored, INFO+)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)

    console_formatter = ColoredFormatter(
        fmt='%(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 2. Main file handler (detailed, DEBUG+)
    main_log_file = session_dir / "agent.log"
    file_handler = logging.FileHandler(main_log_file, encoding='utf-8')
    file_handler.setLevel(file_level)

    file_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # 3. Error log (ERROR+)
    error_log_file = session_dir / "errors.log"
    error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)

    # 4. DBOS workflow log (workflow-specific)
    workflow_log_file = session_dir / "workflow.log"
    workflow_handler = logging.FileHandler(workflow_log_file, encoding='utf-8')
    workflow_handler.setLevel(logging.INFO)

    workflow_formatter = logging.Formatter(
        fmt='%(asctime)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    workflow_handler.setFormatter(workflow_formatter)

    # Only add workflow logs to the workflow logger
    workflow_logger = logging.getLogger('research_agent.durable')
    workflow_logger.addHandler(workflow_handler)

    # 5. Sandbox operations log
    sandbox_log_file = session_dir / "sandbox.log"
    sandbox_handler = logging.FileHandler(sandbox_log_file, encoding='utf-8')
    sandbox_handler.setLevel(logging.DEBUG)
    sandbox_handler.setFormatter(file_formatter)

    sandbox_logger = logging.getLogger('research_agent.sandbox')
    sandbox_logger.addHandler(sandbox_handler)

    # Log startup
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("Durable Research Agent - Logging Initialized")
    logger.info("=" * 80)
    logger.info(f"Session directory: {session_dir}")
    logger.info(f"Main log: {main_log_file}")
    logger.info(f"Error log: {error_log_file}")
    logger.info(f"Workflow log: {workflow_log_file}")
    logger.info(f"Sandbox log: {sandbox_log_file}")
    logger.info("=" * 80)

    return session_dir


def log_system_info():
    """Log system and environment information."""
    import platform
    import os

    logger = logging.getLogger(__name__)

    logger.info("System Information:")
    logger.info(f"  Platform: {platform.system()} {platform.release()}")
    logger.info(f"  Python: {platform.python_version()}")
    logger.info(f"  Working directory: {os.getcwd()}")

    # Check environment variables (without exposing secrets)
    env_vars = {
        "ANTHROPIC_API_KEY": "SET" if os.getenv("ANTHROPIC_API_KEY") else "NOT SET",
        "E2B_API_KEY": "SET" if os.getenv("E2B_API_KEY") else "NOT SET",
        "DATABASE_URL": "SET" if os.getenv("DATABASE_URL") else "NOT SET",
    }

    logger.info("Environment Variables:")
    for var, status in env_vars.items():
        logger.info(f"  {var}: {status}")


def log_workflow_start(workflow_name: str, params: dict):
    """
    Log the start of a DBOS workflow.

    Args:
        workflow_name: Name of the workflow
        params: Workflow parameters
    """
    logger = logging.getLogger('research_agent.durable')

    logger.info("=" * 80)
    logger.info(f"WORKFLOW START: {workflow_name}")
    logger.info("=" * 80)

    for key, value in params.items():
        # Truncate long values
        if isinstance(value, str) and len(value) > 100:
            value = value[:100] + "..."
        elif isinstance(value, list) and len(value) > 10:
            value = f"[{len(value)} items]"

        logger.info(f"  {key}: {value}")

    logger.info("=" * 80)


def log_workflow_step(step_name: str, status: str, details: Optional[dict] = None):
    """
    Log a workflow step completion.

    Args:
        step_name: Name of the step
        status: Status (success, failed, skipped)
        details: Additional details
    """
    logger = logging.getLogger('research_agent.durable')

    status_symbol = {
        'success': '✓',
        'failed': '✗',
        'skipped': '→',
        'running': '⋯'
    }.get(status, '?')

    logger.info(f"{status_symbol} STEP: {step_name} [{status.upper()}]")

    if details:
        for key, value in details.items():
            logger.info(f"    {key}: {value}")


def log_workflow_complete(workflow_name: str, summary: dict):
    """
    Log workflow completion.

    Args:
        workflow_name: Name of the workflow
        summary: Summary statistics
    """
    logger = logging.getLogger('research_agent.durable')

    logger.info("=" * 80)
    logger.info(f"WORKFLOW COMPLETE: {workflow_name}")
    logger.info("=" * 80)

    for key, value in summary.items():
        logger.info(f"  {key}: {value}")

    logger.info("=" * 80)


def log_sandbox_operation(operation: str, agent_id: str, details: Optional[dict] = None):
    """
    Log a sandbox operation.

    Args:
        operation: Operation name (create, execute, close, etc.)
        agent_id: Agent identifier
        details: Additional details
    """
    logger = logging.getLogger('research_agent.sandbox')

    logger.info(f"[{agent_id}] {operation.upper()}")

    if details:
        for key, value in details.items():
            logger.debug(f"  {key}: {value}")


def log_error_with_context(error: Exception, context: dict):
    """
    Log an error with full context for debugging.

    Args:
        error: Exception that occurred
        context: Contextual information
    """
    logger = logging.getLogger(__name__)

    logger.error("=" * 80)
    logger.error(f"ERROR: {type(error).__name__}")
    logger.error(f"Message: {str(error)}")
    logger.error("=" * 80)

    logger.error("Context:")
    for key, value in context.items():
        logger.error(f"  {key}: {value}")

    logger.error("=" * 80)

    # Log full traceback
    import traceback
    logger.error("Traceback:")
    logger.error(traceback.format_exc())
    logger.error("=" * 80)
