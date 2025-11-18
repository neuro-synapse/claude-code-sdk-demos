"""Durable Research Agent with E2B Sandbox Integration.

Combines:
- DBOS durable workflows (fault tolerance, recovery)
- E2B sandboxes (isolated execution)
- Claude Agent SDK (sub-agent coordination)

Each sub-agent runs in its own isolated sandbox with:
- Full tool library access
- Independent internet connection
- Fresh context window
- Complete isolation (Firecracker microVM)

Workflows are durable - they can recover from any failure and continue
from the last completed step, ensuring no research work is lost.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from dbos import DBOS

from research_agent.sandbox import E2BSandboxManager, SandboxedAgentExecutor, ParallelAgentExecutor
from research_agent.durable import DurableResearchWorkflow, ResearchTask
from research_agent.utils.logging_config import (
    setup_logging,
    log_system_info,
    log_workflow_start,
    log_workflow_step,
    log_workflow_complete,
    log_error_with_context
)

# Load environment variables
load_dotenv()


def check_environment():
    """
    Check that all required environment variables are set.

    Returns:
        Tuple of (success, missing_vars)
    """
    required = {
        "ANTHROPIC_API_KEY": "Get your key at: https://console.anthropic.com/settings/keys",
        "E2B_API_KEY": "Get your key at: https://e2b.dev/dashboard",
        "DATABASE_URL": "PostgreSQL connection string for DBOS (e.g., postgresql://user:pass@localhost/dbname)"
    }

    missing = []
    for var, hint in required.items():
        if not os.getenv(var):
            missing.append((var, hint))

    return len(missing) == 0, missing


async def run_durable_wide_research(items: list[str], session_dir: Path):
    """
    Run wide research with durable execution and sandboxed agents.

    Args:
        items: List of items to research
        session_dir: Session directory for logs

    Returns:
        Workflow result
    """
    import logging
    logger = logging.getLogger(__name__)

    # Log workflow start
    log_workflow_start("wide_research", {
        "items": items,
        "num_items": len(items),
        "session_dir": str(session_dir)
    })

    try:
        # Initialize components
        logger.info("Initializing E2B Sandbox Manager")
        sandbox_manager = E2BSandboxManager()

        logger.info("Initializing Sandboxed Agent Executor")
        agent_executor = SandboxedAgentExecutor(
            sandbox_manager=sandbox_manager,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )

        logger.info("Initializing Parallel Agent Executor")
        parallel_executor = ParallelAgentExecutor(agent_executor)

        # Initialize DBOS workflow
        logger.info("Initializing DBOS Durable Workflow")
        workflow = DurableResearchWorkflow(sandbox_manager=sandbox_manager)

        # Research prompt template
        prompt_template = """
Research the following item comprehensively: {item}

Gather information about:
- Overview and description
- Key features or characteristics
- Recent developments or news
- Market position or relevance
- Notable facts or insights

Write your findings in a clear, structured markdown document.
Focus on accuracy and comprehensive coverage.
"""

        # Execute durable workflow
        log_workflow_step("parallel_research", "running", {
            "items": items,
            "agents": len(items)
        })

        # Run the durable workflow
        result = workflow.run_wide_research(
            items=items,
            research_prompt_template=prompt_template
        )

        # Log completion
        log_workflow_complete("wide_research", {
            "total_items": len(items),
            "successful": result["summary"]["successful"],
            "failed": result["summary"]["failed"],
            "output_files": len(result["summary"]["output_files"])
        })

        # Cleanup
        logger.info("Cleaning up sandboxes")
        sandbox_manager.close_all()

        return result

    except Exception as e:
        log_error_with_context(e, {
            "items": items,
            "session_dir": str(session_dir),
            "workflow": "wide_research"
        })
        raise


async def run_durable_single_research(topic: str, session_dir: Path):
    """
    Run single-topic research with durable execution.

    Args:
        topic: Research topic
        session_dir: Session directory for logs

    Returns:
        Workflow result
    """
    import logging
    logger = logging.getLogger(__name__)

    # Decompose topic into subtopics (simplified)
    # In production, the lead agent would do this
    subtopics = [
        f"{topic} - Overview",
        f"{topic} - Current State",
        f"{topic} - Future Outlook"
    ]

    log_workflow_start("single_research", {
        "topic": topic,
        "subtopics": subtopics,
        "session_dir": str(session_dir)
    })

    try:
        # Initialize components
        sandbox_manager = E2BSandboxManager()

        agent_executor = SandboxedAgentExecutor(
            sandbox_manager=sandbox_manager,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )

        workflow = DurableResearchWorkflow(sandbox_manager=sandbox_manager)

        # Execute workflow
        result = workflow.run_single_research(
            topic=topic,
            subtopics=subtopics
        )

        log_workflow_complete("single_research", {
            "topic": topic,
            "subtopics": len(subtopics),
            "successful": result["summary"]["successful"],
            "failed": result["summary"]["failed"]
        })

        # Cleanup
        sandbox_manager.close_all()

        return result

    except Exception as e:
        log_error_with_context(e, {
            "topic": topic,
            "session_dir": str(session_dir),
            "workflow": "single_research"
        })
        raise


async def interactive_mode():
    """Interactive chat mode for durable research agent."""
    import logging
    logger = logging.getLogger(__name__)

    print("\n" + "=" * 80)
    print("🔬 DURABLE RESEARCH AGENT (E2B + DBOS)")
    print("=" * 80)
    print("\nFeatures:")
    print("  ✓ Durable workflows (recovers from any failure)")
    print("  ✓ Isolated sandboxes (each sub-agent in E2B sandbox)")
    print("  ✓ Parallel execution (all agents run simultaneously)")
    print("  ✓ Comprehensive logging (track everything)")
    print("\nExamples:")
    print('  "Research Apple, Microsoft, Google" (wide research)')
    print('  "Research quantum computing" (single topic)')
    print("\nType 'exit' or 'quit' to end.\n")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ["exit", "quit", "q"]:
            break

        # Parse input to determine mode
        # Simple heuristic: comma-separated = wide research
        if "," in user_input:
            items = [item.strip() for item in user_input.split(",")]
            items = [item for item in items if item]  # Remove empty

            logger.info(f"Detected wide research mode: {len(items)} items")

            # Create session directory
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_dir = Path("logs") / f"session_{timestamp}"
            session_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n🚀 Starting wide research for {len(items)} items...")
            print(f"📁 Logs: {session_dir}")

            result = await run_durable_wide_research(items, session_dir)

            print(f"\n✓ Research complete!")
            print(f"  Successful: {result['summary']['successful']}/{result['summary']['total']}")
            print(f"  Output files: {len(result['summary']['output_files'])}")

        else:
            topic = user_input
            logger.info(f"Detected single research mode: {topic}")

            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_dir = Path("logs") / f"session_{timestamp}"
            session_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n🚀 Starting research on: {topic}")
            print(f"📁 Logs: {session_dir}")

            result = await run_durable_single_research(topic, session_dir)

            print(f"\n✓ Research complete!")
            print(f"  Subtopics: {len(result['subtopics'])}")
            print(f"  Successful: {result['summary']['successful']}/{result['summary']['total']}")

    print("\n👋 Goodbye!")


def main():
    """Main entry point for durable research agent."""

    # Setup logging
    session_dir = setup_logging()
    log_system_info()

    # Check environment
    env_ok, missing = check_environment()

    if not env_ok:
        print("\n❌ Missing required environment variables:\n")
        for var, hint in missing:
            print(f"  {var}")
            print(f"    {hint}\n")

        print("Set these in your .env file or export them in your shell.\n")
        sys.exit(1)

    print("✓ Environment configured")

    # Initialize DBOS
    try:
        # DBOS configuration
        # In production, this would read from dbos-config.yaml
        DBOS.launch()
        print("✓ DBOS initialized (durable execution enabled)")
    except Exception as e:
        print(f"\n⚠️  DBOS initialization failed: {e}")
        print("Note: DBOS requires PostgreSQL. Continuing without durability...\n")

    # Run interactive mode
    try:
        asyncio.run(interactive_mode())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print(f"\n📁 Session logs: {session_dir}")


if __name__ == "__main__":
    main()
