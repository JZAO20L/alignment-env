# SPDX-License-Identifier: BSD-3-Clause

"""
Red Blue Env Environment Implementation.

A simple test environment that echoes back messages sent to it.
Perfect for testing HTTP server infrastructure.
"""

from typing import Any, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import RedBlueAction, RedBlueObservation
except ImportError:
    from models import RedBlueAction, RedBlueObservation


class RedBlueEnvironment(Environment):
    """
    A simple echo environment that echoes back messages.

    This environment is designed for testing the HTTP server infrastructure.
    It maintains minimal state and simply echoes back whatever message it receives.

    Example:
        >>> env = RedBlueEnvironment()
        >>> obs = env.reset()
        >>> print(obs.echoed_message)  # "Red Blue Env environment ready!"
        >>>
        >>> obs = env.step(RedBlueAction(message="Hello"))
        >>> print(obs.echoed_message)  # "Hello"
        >>> print(obs.message_length)  # 5
    """

    # Enable concurrent WebSocket sessions.
    # Set to True if your environment isolates state between instances.
    # When True, multiple WebSocket clients can connect simultaneously, each
    # getting their own environment instance (when using factory mode in app.py).
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        """Initialize the red_blue_env environment."""
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count = 0

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> RedBlueObservation:
        """
        Reset the environment.

        Args:
            seed: Optional random seed. Seed any randomness in your environment from it.
            episode_id: Optional episode ID to use. A new UUID is generated if omitted.
            **kwargs: Additional reset options.

        Returns:
            RedBlueObservation with a ready message
        """
        self._state = State(
            episode_id=episode_id if episode_id is not None else str(uuid4()),
            step_count=0,
        )
        self._reset_count += 1

        return RedBlueObservation(
            echoed_message="Red Blue Env environment ready!",
            message_length=0,
            done=False,
            reward=0.0,
        )

    def step(self, action: RedBlueAction) -> RedBlueObservation:  # type: ignore[override]
        """
        Execute a step in the environment by echoing the message.

        Args:
            action: RedBlueAction containing the message to echo

        Returns:
            RedBlueObservation with the echoed message and its length
        """
        self._state.step_count += 1

        message = action.message
        length = len(message)

        # Simple bounded reward: longer messages get higher rewards up to 1.0
        reward = min(length * 0.1, 1.0)

        return RedBlueObservation(
            echoed_message=message,
            message_length=length,
            done=False,
            reward=reward,
            metadata={"original_message": message, "step": self._state.step_count},
        )

    @property
    def state(self) -> State:
        """
        Get the current environment state.

        Returns:
            Current State with episode_id and step_count
        """
        return self._state
