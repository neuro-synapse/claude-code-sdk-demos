"""
Example usage of the Durable Research Agent with E2B sandboxes and DBOS workflows.

This demonstrates:
1. Wide research across multiple items
2. Automatic recovery from failures
3. Comprehensive logging
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

from research_agent.sandbox import E2BSandboxManager, SandboxedAgentExecutor
from research_agent.durable import DurableResearchWorkflow
from research_agent.utils.logging_config import (
    setup_logging,
    log_workflow_start,
    log_workflow_complete
)

# Load environment variables
load_dotenv()


async def example_wide_research():
    """
    Example: Wide research across multiple tech companies.

    Each company gets its own isolated sandbox for research.
    If the workflow fails, it automatically recovers.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE: Wide Research with E2B Sandboxes + DBOS")
    print("=" * 80)

    # Setup logging
    session_dir = setup_logging()
    print(f"\n📁 Logs will be saved to: {session_dir}\n")

    # Items to research
    items = ["Apple", "Microsoft", "Google"]

    # Research prompt template
    prompt_template = """
Research {item} comprehensively.

Please provide:
1. Company overview
2. Recent news and developments
3. Market position
4. Key products and services

Write your findings in clear, structured markdown.
"""

    # Initialize components
    print("🔧 Initializing components...")

    sandbox_manager = E2BSandboxManager()
    print("  ✓ E2B Sandbox Manager")

    agent_executor = SandboxedAgentExecutor(
        sandbox_manager=sandbox_manager,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    print("  ✓ Sandboxed Agent Executor")

    workflow = DurableResearchWorkflow(sandbox_manager=sandbox_manager)
    print("  ✓ DBOS Durable Workflow")

    # Log workflow start
    log_workflow_start("example_wide_research", {
        "items": items,
        "num_items": len(items)
    })

    print(f"\n🚀 Starting research for {len(items)} items...")
    print(f"Items: {', '.join(items)}\n")

    try:
        # Execute durable workflow
        result = workflow.run_wide_research(
            items=items,
            research_prompt_template=prompt_template
        )

        # Log completion
        log_workflow_complete("example_wide_research", {
            "total": len(items),
            "successful": result["summary"]["successful"],
            "failed": result["summary"]["failed"]
        })

        # Display results
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        print(f"\nTotal items: {len(items)}")
        print(f"Successful: {result['summary']['successful']}")
        print(f"Failed: {result['summary']['failed']}")
        print(f"\nOutput files:")
        for output_file in result["summary"]["output_files"]:
            print(f"  - {output_file}")

        print("\n" + "=" * 80)
        print("✓ Research complete!")
        print("=" * 80)

    finally:
        # Cleanup
        print("\n🧹 Cleaning up sandboxes...")
        sandbox_manager.close_all()
        print("  ✓ All sandboxes closed")

    print(f"\n📁 Session logs: {session_dir}")
    print("  - agent.log (all debug logs)")
    print("  - workflow.log (DBOS workflow steps)")
    print("  - sandbox.log (E2B operations)")
    print("  - errors.log (errors only)")


async def example_failure_recovery():
    """
    Example: Demonstrate failure recovery.

    This example shows how DBOS automatically recovers from failures.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE: Failure Recovery")
    print("=" * 80)

    print("\nThis example demonstrates DBOS workflow recovery.")
    print("Steps:")
    print("  1. Start research on multiple items")
    print("  2. Simulate a failure (kill the process)")
    print("  3. Restart the workflow")
    print("  4. DBOS resumes from last completed step")

    print("\n📝 To test recovery:")
    print("  1. Run this script")
    print("  2. Kill it mid-execution (Ctrl+C)")
    print("  3. Run it again")
    print("  4. Notice it resumes from where it left off")


async def example_sandbox_isolation():
    """
    Example: Demonstrate sandbox isolation.

    Shows that each agent runs in complete isolation.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE: Sandbox Isolation")
    print("=" * 80)

    print("\nDemonstrating isolated sandbox execution...")

    sandbox_manager = E2BSandboxManager()

    # Create two sandboxes
    print("\n1. Creating two isolated sandboxes...")

    sandbox1 = sandbox_manager.create_sandbox("researcher", "AGENT-1")
    sandbox2 = sandbox_manager.create_sandbox("researcher", "AGENT-2")

    print(f"  ✓ Sandbox 1: {sandbox1.sandbox_id}")
    print(f"  ✓ Sandbox 2: {sandbox2.sandbox_id}")

    # Execute code in each sandbox
    print("\n2. Executing code in each sandbox...")

    # Sandbox 1: Set variable x = 10
    result1 = sandbox_manager.execute_code("AGENT-1", "x = 10; print(f'Sandbox 1: x = {x}')")
    print(f"  {result1['stdout'].strip()}")

    # Sandbox 2: Set variable x = 20
    result2 = sandbox_manager.execute_code("AGENT-2", "x = 20; print(f'Sandbox 2: x = {x}')")
    print(f"  {result2['stdout'].strip()}")

    # Verify isolation
    print("\n3. Verifying isolation...")

    # Sandbox 1: x should still be 10
    result1 = sandbox_manager.execute_code("AGENT-1", "print(f'Sandbox 1: x = {x}')")
    print(f"  {result1['stdout'].strip()}")

    # Sandbox 2: x should still be 20
    result2 = sandbox_manager.execute_code("AGENT-2", "print(f'Sandbox 2: x = {x}')")
    print(f"  {result2['stdout'].strip()}")

    print("\n✓ Sandboxes are completely isolated!")
    print("  Each agent has its own environment, variables, and state.")

    # Cleanup
    sandbox_manager.close_all()


async def main():
    """Run all examples."""

    print("\n" + "=" * 80)
    print("DURABLE RESEARCH AGENT - EXAMPLES")
    print("=" * 80)

    # Check environment
    required = ["ANTHROPIC_API_KEY", "E2B_API_KEY", "DATABASE_URL"]
    missing = [var for var in required if not os.getenv(var)]

    if missing:
        print("\n❌ Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nPlease set these in your .env file.")
        return

    print("\n✓ Environment configured")

    # Menu
    print("\nAvailable examples:")
    print("  1. Wide research (with E2B + DBOS)")
    print("  2. Failure recovery (how DBOS recovers)")
    print("  3. Sandbox isolation (how E2B isolates agents)")
    print("  4. Run all examples")

    choice = input("\nChoose an example (1-4): ").strip()

    if choice == "1":
        await example_wide_research()
    elif choice == "2":
        await example_failure_recovery()
    elif choice == "3":
        await example_sandbox_isolation()
    elif choice == "4":
        await example_failure_recovery()
        await example_sandbox_isolation()
        await example_wide_research()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())
