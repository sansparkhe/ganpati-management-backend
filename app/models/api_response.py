from datetime import UTC, datetime
from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    code: int = 200
    message: str = "OK"
    response: object | None = None
    success: bool = True
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def ok(cls, response=None, message="OK"):
        return cls(message=message, response=response)

    @classmethod
    def created(cls, response=None, message="Created"):
        return cls(code=201, message=message, response=response)

    @classmethod
    def fail(cls, message, code=400, error="BAD_REQUEST"):
        return cls(
            code=code,
            message=message,
            success=False,
            error=error,
        )