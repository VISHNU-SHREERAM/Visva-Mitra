"""Contains pydantic base classes for requests and responses."""
from pydantic import BaseModel, Field


class CommandResponse(BaseModel):
    """Gives command along with additional information.

    Parameters
    ----------
    command: str
    additional: str

    command is the base reduced command
    additional is the additional information associated with the command in the user query

    """

    command: str = Field(..., strict=True)
    additional: str = Field(..., strict=True)

class CommandListResponse(BaseModel):
    """Gives a list of CommandResponse.

    Parameters
    ----------
    commands: list[CommandResponse]

    commands is the list of CommandResponse objects

    """

    commands: list[CommandResponse] = Field(..., strict=True)

class FinalResponse(BaseModel):
    """Gives transcription as response and message.

    Parameters
    ----------
    response: str
    message: str

    response is the transcription text
    message is the transcription text

    """

    response: str = Field(..., strict=True)
    message: str = Field(..., strict=True)
