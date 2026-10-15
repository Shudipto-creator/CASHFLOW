"""Base agent class for all AI agents"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging
import time

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all agents"""

    def __init__(self, nova_client):
        """
        Initialize agent with Nova client

        Args:
            nova_client: NovaClient instance for model invocation
        """
        self.nova_client = nova_client
        self.agent_name = self.__class__.__name__

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent logic

        Args:
            context: Dictionary with relevant data for processing

        Returns:
            Dictionary with agent results
        """
        pass

    @abstractmethod
    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """
        Build agent-specific prompt from context

        Args:
            context: Dictionary with context data

        Returns:
            Formatted prompt string
        """
        pass

    def _validate_output(self, output: Dict[str, Any]) -> bool:
        """
        Validate agent output structure

        Args:
            output: Agent output dictionary

        Returns:
            True if valid, False otherwise
        """
        # Base validation - check for error
        if "error" in output:
            logger.error(f"{self.agent_name} returned error: {output['error']}")
            return False

        return True

    def run_with_retry(
        self,
        context: Dict[str, Any],
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        reasoning_effort: str,
    ) -> tuple[Dict[str, Any], int]:
        """
        Run agent with automatic retry and timing

        Args:
            context: Execution context
            system_prompt: System prompt for agent
            temperature: Temperature setting
            max_tokens: Max token limit
            reasoning_effort: Reasoning effort level

        Returns:
            Tuple of (result_dict, execution_time_ms)
        """
        start_time = time.time()

        try:
            # Build prompt
            prompt = self._build_prompt(context)

            # Invoke Nova model
            result = self.nova_client.invoke_agent(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
            )

            # Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Validate output
            if not self._validate_output(result):
                logger.warning(f"{self.agent_name} output validation failed")

            logger.info(f"{self.agent_name} completed in {execution_time_ms}ms")

            return result, execution_time_ms

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"{self.agent_name} failed: {str(e)}")
            return {"error": str(e)}, execution_time_ms
