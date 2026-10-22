from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Any


class IncomingRequest(BaseModel):
    weight: int = Field(ge=1, le=20)
    scenario: Literal['normal', 'partial', 'retry', 'all_down']


class ProviderResponsePositive(BaseModel):
    model_config = ConfigDict(strict=True)

    response_type: Literal['positive'] = Field(default="positive", exclude=True)
    provider_id: str
    price_tenge: int = Field(ge=1)
    days: int = Field(ge=1, le=30)


class ProviderResponseNegative(BaseModel):
    model_config = ConfigDict(strict=True)

    response_type: Literal['negative'] = Field(default="negative", exclude=True)
    provider_id: str
    detail: Any


ProviderResponse = ProviderResponsePositive | ProviderResponseNegative

