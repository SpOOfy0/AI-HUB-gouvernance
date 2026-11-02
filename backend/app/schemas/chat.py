from pydantic import BaseModel, Field

from app.core.enums import Level


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: int | None = None
    model_id: int | None = Field(default=None, description="None = mode automatique")
    declared_level: Level | None = Field(default=None, description="Peut relever le niveau, jamais l'abaisser")
    deep_reasoning: bool = False
    accept_private_fallback: bool = Field(default=False, description="Mode manuel : basculer vers un modèle privé si refus")


class ClassifyIn(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    declared_level: Level | None = None
