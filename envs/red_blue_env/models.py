# SPDX-License-Identifier: BSD-3-Clause

"""
Data models for the Red Blue Env Environment.

The red_blue_env environment is a simple test environment that echoes back messages.
"""

from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class RedBlueAction(Action):
    """Action for the Red Blue Env environment - just a message to echo."""

    message: str = Field(..., description="Message to echo back")


class RedBlueObservation(Observation):
    """Observation from the Red Blue Env environment - the echoed message."""

    echoed_message: str = Field(default="", description="The echoed message")
    message_length: int = Field(default=0, description="Length of the echoed message")
