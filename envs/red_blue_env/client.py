# SPDX-License-Identifier: BSD-3-Clause

"""Red Blue Env Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import RedBlueAction, RedBlueObservation


class RedBlueEnv(
    EnvClient[RedBlueAction, RedBlueObservation, State]
):
    """
    Client for the Red Blue Env Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> # Connect to a running server (.sync() for sync use)
        >>> with RedBlueEnv(base_url="http://localhost:8000").sync() as client:
        ...     result = client.reset()
        ...     print(result.observation.echoed_message)
        ...
        ...     result = client.step(RedBlueAction(message="Hello!"))
        ...     print(result.observation.echoed_message)

    Example with Docker:
        >>> # Automatically start container and connect (.sync() for sync use)
        >>> client = RedBlueEnv.from_docker_image("openenv-red_blue:latest").sync()
        >>> try:
        ...     result = client.reset()
        ...     result = client.step(RedBlueAction(message="Test"))
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: RedBlueAction) -> Dict:
        """
        Convert RedBlueAction to JSON payload for step message.

        Args:
            action: RedBlueAction instance

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        return {
            "message": action.message,
        }

    def _parse_result(self, payload: Dict) -> StepResult[RedBlueObservation]:
        """
        Parse server response into StepResult[RedBlueObservation].

        Args:
            payload: JSON response data from server

        Returns:
            StepResult with RedBlueObservation
        """
        obs_data = payload.get("observation", {})
        observation = RedBlueObservation(
            echoed_message=obs_data.get("echoed_message", ""),
            message_length=obs_data.get("message_length", 0),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=payload.get("metadata", obs_data.get("metadata", {})),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
            metadata=payload.get("metadata"),
        )

    def _parse_state(self, payload: Dict) -> State:
        """
        Parse server response into State object.

        Args:
            payload: JSON response from state request

        Returns:
            State object with episode_id and step_count
        """
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
