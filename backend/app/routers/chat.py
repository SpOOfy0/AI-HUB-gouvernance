"""Chat (playground) : passe exclusivement par la passerelle."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import get_current_user
from app.core.enums import App, Hosting, Role, Severity
from app.core.rate_limit import limiter
from app.core.request_context import get_request_id
from app.db import get_db
from app.models import Conversation, LlmModel, Message, User
from app.providers.base import ProviderFactory
from app.providers.factory import get_provider_factory, is_model_available, ollama_available
from app.schemas.chat import ChatIn
from app.services import audit_service, llm_gateway

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat/completions")
def chat(body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db),
         provider_factory: ProviderFactory = Depends(get_provider_factory)) -> dict:
    if not limiter.allow(f"chat:{user.id}", get_settings().rate_limit_chat_per_minute):
        audit_service.log_event(db, "RATE_LIMITED", category="security", severity=Severity.WARNING, status="DENIED",
                                user_id=user.id, request_id=get_request_id(), details={"route": "chat"})
        db.commit()
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de requêtes, réessayez dans une minute.")
    app = App.DEVELOPER if user.role == Role.DEVELOPER else App.CHAT
    inp = llm_gateway.ChatInput(
        message=body.message, conversation_id=body.conversation_id, model_id=body.model_id,
        declared_level=body.declared_level, deep_reasoning=body.deep_reasoning,
        accept_private_fallback=body.accept_private_fallback, app=app,
    )
    return llm_gateway.handle_chat(db, user, inp, provider_factory, get_request_id())


@router.get("/models/available")
def available_models(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Modèles actifs autorisés pour mon rôle (le choix final reste soumis à la classification)."""
    settings = get_settings()
    models = db.scalars(select(LlmModel).where(LlmModel.is_active.is_(True)).order_by(LlmModel.id)).unique()
    ollama_up = ollama_available()
    out = []
    for m in models:
        if user.role not in (m.allowed_roles or []):
            continue
        # Simulé = mode démo ET pas de vrai backend (Ollama joignable pour les modèles privés).
        simulated = settings.demo_mode and not (m.hosting == Hosting.PRIVATE and ollama_up)
        out.append({
            "id": m.id, "display_name": m.display_name, "litellm_name": m.litellm_name, "provider": m.provider.name,
            "hosting": m.hosting, "max_classification": m.max_classification, "tier": m.tier, "simulated": simulated,
            "available": is_model_available(m),
            "price": {"input_per_mtok": str(m.price.input_per_mtok), "output_per_mtok": str(m.price.output_per_mtok),
                      "is_demo": m.price.is_demo} if m.price else None,
        })
    return out


@router.get("/conversations")
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    convs = db.scalars(select(Conversation).where(Conversation.user_id == user.id)
                       .order_by(Conversation.updated_at.desc()).limit(100))
    return [{"id": c.id, "title": c.title, "max_classification": c.max_classification,
             "updated_at": c.updated_at.isoformat()} for c in convs]


def _own_conversation(db: Session, user: User, conversation_id: int) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:  # pas de fuite d'existence : même 404
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation introuvable")
    return conv


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    conv = _own_conversation(db, user, conversation_id)
    return {
        "id": conv.id, "title": conv.title, "max_classification": conv.max_classification,
        "messages": [{"id": m.id, "role": m.role, "content": m.content, "classification": m.classification,
                      "routing": m.routing, "created_at": m.created_at.isoformat()} for m in conv.messages],
    }


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    conv = _own_conversation(db, user, conversation_id)
    db.execute(delete(Message).where(Message.conversation_id == conv.id))
    db.delete(conv)
    audit_service.log_event(db, "CONVERSATION_DELETED", category="ai", user_id=user.id, request_id=get_request_id(),
                            details={"conversation_id": conversation_id})
    db.commit()
