"""
Python implementation of the AI Client for Claude Code SDK integration.
This module provides a wrapper around the Claude Code SDK with email-specific tools and security hooks.
"""

import os
import asyncio
from typing import Dict, List, Optional, Union, Any, AsyncGenerator, TypedDict
from dataclasses import dataclass, field
from pathlib import Path
import re

# Note: These would be imported from the actual Claude Code SDK Python package
# For this example, I'm defining the interfaces that would exist
from typing import Protocol, runtime_checkable

# Type definitions (equivalent to TypeScript interfaces)
@runtime_checkable
class SDKMessage(Protocol):
    """Protocol defining the structure of SDK messages"""
    type: str
    subtype: Optional[str] = None
    total_cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None

@runtime_checkable
class SDKUserMessage(Protocol):
    """Protocol defining the structure of user messages"""
    content: str

class HookJSONOutput(TypedDict, total=False):
    """Type definition for hook output"""
    continue_processing: bool
    decision: Optional[str]
    stop_reason: Optional[str]

@dataclass
class AIQueryOptions:
    """Configuration options for AI queries"""
    max_turns: int = 100
    cwd: Optional[str] = None
    model: str = "opus"
    allowed_tools: List[str] = field(default_factory=list)
    append_system_prompt: Optional[str] = None
    mcp_servers: Optional[Dict[str, Any]] = None
    hooks: Optional[Dict[str, Any]] = None

class AIClient:
    """
    AI Client wrapper for Claude Code SDK with email-specific functionality.

    This class provides:
    - Integration with Claude Code SDK
    - Email-specific tools and prompts
    - Security hooks to prevent unauthorized file operations
    - Streaming and single-query interfaces
    """

    def __init__(self, options: Optional[Dict[str, Any]] = None):
        """
        Initialize the AI Client with default options and security configurations.

        Args:
            options: Optional dictionary of configuration overrides
        """
        # Import email-specific modules (these would be equivalent to the TS imports)
        from .email_agent_prompt import EMAIL_AGENT_PROMPT
        from .custom_tools import custom_server

        # Set up default working directory
        default_cwd = os.path.join(os.getcwd(), 'agent')

        # Define default allowed tools (equivalent to TS array)
        default_allowed_tools = [
            "Task", "Bash", "Glob", "Grep", "LS", "ExitPlanMode",
            "Read", "Edit", "MultiEdit", "Write", "NotebookEdit",
            "WebFetch", "TodoWrite", "WebSearch", "BashOutput",
            "KillBash", "mcp__email__search_inbox", "mcp__email__read_emails"
        ]

        # Create default configuration
        self.default_options = AIQueryOptions(
            max_turns=100,
            cwd=default_cwd,
            model="opus",
            allowed_tools=default_allowed_tools,
            append_system_prompt=EMAIL_AGENT_PROMPT,
            mcp_servers={"email": custom_server},
            hooks=self._create_security_hooks()
        )

        # Apply any user-provided option overrides
        if options:
            self._apply_option_overrides(options)

    def _create_security_hooks(self) -> Dict[str, Any]:
        """
        Create security hooks to prevent unauthorized file operations.

        This is equivalent to the TypeScript hooks configuration that prevents
        writing .js/.ts files outside the custom_scripts directory.

        Returns:
            Dictionary containing hook configurations
        """
        async def pre_tool_use_hook(input_data: Dict[str, Any]) -> HookJSONOutput:
            """
            Security hook that validates file operations before execution.

            Args:
                input_data: Dictionary containing tool_name and tool_input

            Returns:
                HookJSONOutput indicating whether to continue or block the operation
            """
            tool_name = input_data.get('tool_name', '')
            tool_input = input_data.get('tool_input', {})

            # Only apply security checks to file modification tools
            if tool_name not in ['Write', 'Edit', 'MultiEdit']:
                return HookJSONOutput(continue_processing=True)

            # Extract file path based on tool type
            file_path = ''
            if tool_name in ['Write', 'Edit']:
                file_path = tool_input.get('file_path', '')
            elif tool_name == 'MultiEdit':
                file_path = tool_input.get('file_path', '')

            # Check if it's a JavaScript/TypeScript file
            file_extension = Path(file_path).suffix.lower()
            if file_extension in ['.js', '.ts']:
                # Define the allowed custom scripts directory
                custom_scripts_path = os.path.join(os.getcwd(), 'agent', 'custom_scripts')

                # Block if file is not in the allowed directory
                if not file_path.startswith(custom_scripts_path):
                    filename = os.path.basename(file_path)
                    return HookJSONOutput(
                        decision='block',
                        stop_reason=f"Script files (.js and .ts) must be written to the custom_scripts directory. "
                                  f"Please use the path: {custom_scripts_path}/{filename}",
                        continue_processing=False
                    )

            return HookJSONOutput(continue_processing=True)

        return {
            'PreToolUse': [
                {
                    'matcher': re.compile(r'Write|Edit|MultiEdit'),
                    'hooks': [pre_tool_use_hook]
                }
            ]
        }

    def _apply_option_overrides(self, options: Dict[str, Any]) -> None:
        """
        Apply user-provided option overrides to default configuration.

        Args:
            options: Dictionary of option overrides
        """
        for key, value in options.items():
            if hasattr(self.default_options, key):
                setattr(self.default_options, key, value)

    async def query_stream(
        self,
        prompt: Union[str, AsyncGenerator[SDKUserMessage, None]],
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[SDKMessage, None]:
        """
        Stream AI responses for real-time interaction.

        This method provides a streaming interface to the Claude Code SDK,
        yielding messages as they arrive for real-time user interfaces.

        Args:
            prompt: User prompt string or async generator of user messages
            options: Optional configuration overrides

        Yields:
            SDKMessage objects as they are received from the AI
        """
        # Merge provided options with defaults
        merged_options = self._merge_options(options)

        try:
            # This would use the actual Claude Code SDK query function
            # For this example, I'm showing the interface structure
            async for message in self._claude_code_query(prompt, merged_options):
                yield message

        except Exception as e:
            # Log error and re-raise
            print(f"Error in query_stream: {e}")
            raise

    async def query_single(
        self,
        prompt: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a single AI query and return all results.

        This method collects all streaming responses into a single result,
        useful for batch processing or when you need the complete response.

        Args:
            prompt: User prompt string
            options: Optional configuration overrides

        Returns:
            Dictionary containing:
            - messages: List of all SDK messages
            - cost: Total cost in USD
            - duration: Total duration in milliseconds
        """
        messages = []
        total_cost = 0.0
        duration = 0

        try:
            async for message in self.query_stream(prompt, options):
                messages.append(message)

                # Extract cost and duration from result messages
                if (hasattr(message, 'type') and message.type == "result" and
                    hasattr(message, 'subtype') and message.subtype == "success"):

                    if hasattr(message, 'total_cost_usd'):
                        total_cost = message.total_cost_usd or 0.0
                    if hasattr(message, 'duration_ms'):
                        duration = message.duration_ms or 0

            return {
                'messages': messages,
                'cost': total_cost,
                'duration': duration
            }

        except Exception as e:
            print(f"Error in query_single: {e}")
            raise

    def _merge_options(self, options: Optional[Dict[str, Any]]) -> AIQueryOptions:
        """
        Merge provided options with default configuration.

        Args:
            options: Optional configuration overrides

        Returns:
            Merged AIQueryOptions object
        """
        if not options:
            return self.default_options

        # Create a copy of default options
        merged = AIQueryOptions(
            max_turns=self.default_options.max_turns,
            cwd=self.default_options.cwd,
            model=self.default_options.model,
            allowed_tools=self.default_options.allowed_tools.copy(),
            append_system_prompt=self.default_options.append_system_prompt,
            mcp_servers=self.default_options.mcp_servers.copy() if self.default_options.mcp_servers else None,
            hooks=self.default_options.hooks.copy() if self.default_options.hooks else None
        )

        # Apply overrides
        for key, value in options.items():
            if hasattr(merged, key):
                setattr(merged, key, value)

        return merged

    async def _claude_code_query(
        self,
        prompt: Union[str, AsyncGenerator[SDKUserMessage, None]],
        options: AIQueryOptions
    ) -> AsyncGenerator[SDKMessage, None]:
        """
        Interface to the actual Claude Code SDK query function.

        This would be replaced with the actual SDK call in a real implementation.

        Args:
            prompt: User prompt or message generator
            options: Query configuration options

        Yields:
            SDKMessage objects from the Claude Code SDK
        """
        # This is a placeholder for the actual Claude Code SDK integration
        # In a real implementation, this would call:
        # from anthropic_claude_code import query
        # async for message in query(prompt=prompt, options=options.__dict__):
        #     yield message

        # For demonstration purposes, yielding a mock message
        class MockMessage:
            def __init__(self, msg_type: str, content: str = ""):
                self.type = msg_type
                self.content = content
                self.subtype = "success" if msg_type == "result" else None
                self.total_cost_usd = 0.001 if msg_type == "result" else None
                self.duration_ms = 1500 if msg_type == "result" else None

        yield MockMessage("assistant", "This is a mock response from the AI client.")
        yield MockMessage("result")

# Example usage and testing
async def main():
    """Example usage of the AI Client"""

    # Initialize the AI client
    client = AIClient()

    # Example 1: Single query
    result = await client.query_single("Search for emails from john@example.com")
    print(f"Single query result: {len(result['messages'])} messages, "
          f"cost: ${result['cost']:.4f}, duration: {result['duration']}ms")

    # Example 2: Streaming query
    print("\nStreaming query:")
    async for message in client.query_stream("Find recent invoices"):
        print(f"Received message type: {message.type}")

if __name__ == "__main__":
    asyncio.run(main())