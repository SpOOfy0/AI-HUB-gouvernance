"""Fournisseur simulé (mode démo). Même interface que les vrais fournisseurs.

Réponse courte plausible préfixée par "[Réponse simulée]", latence aléatoire, tokens estimés.
Aucun appel réseau.
"""
import random
import re
import time

from app.config import get_settings
from app.models import LlmModel
from app.providers.base import ProviderError, ProviderResult
from app.services.cost_service import estimate_tokens
from app.services.dlp_service import normalize

_CANNED = [
    (("fob", "cif", "incoterm", "exw", "ddp", "dap"),
     "Les Incoterms 2020 répartissent coûts et risques entre vendeur et acheteur. En FOB, le transfert de risque "
     "a lieu quand la marchandise est à bord du navire au port d'embarquement ; en CIF, le vendeur paie en plus "
     "le fret et une assurance minimale jusqu'au port de destination, mais le risque est transféré au même moment."),
    (("connaissement", "b/l", "bill of lading"),
     "Le connaissement (B/L) est à la fois un reçu de la marchandise, une preuve du contrat de transport et un titre "
     "représentatif : le B/L original négociable permet de retirer la marchandise auprès de l'armateur."),
    (("douane", "declaration", "dédouanement", "dedouanement", "eori"),
     "Une déclaration en douane nécessite le numéro EORI de l'opérateur, le classement tarifaire (code SH), "
     "la valeur en douane, l'origine des marchandises et le régime douanier demandé."),
    (("code sh", "nomenclature", "tarif douanier"),
     "La nomenclature du Système Harmonisé (SH) classe les marchandises sur 6 chiffres, complétés à 8 chiffres "
     "dans la Nomenclature combinée de l'UE et à 10 chiffres dans le TARIC."),
    (("surestarie", "demurrage", "detention"),
     "Les surestaries (demurrage) sont facturées par l'armateur quand le conteneur reste au terminal au-delà de la "
     "franchise ; les frais de détention s'appliquent quand il reste hors du terminal chez le client."),
    (("conteneur", "container", "evp", "teu"),
     "Un numéro de conteneur ISO 6346 comporte 4 lettres (code propriétaire + catégorie), 6 chiffres et un chiffre "
     "de contrôle. Un 40' représente 2 EVP."),
    (("tarif", "tarifs", "cotation", "fret", "armateur"),
     "Pour analyser une cotation fret, comparez le taux de base (BAS), les surcharges (BAF, CAF, THC), les "
     "franchises de surestaries et la validité de l'offre. Un tableau par armateur et par ligne facilite la comparaison."),
    (("procedure", "dossier"),
     "Synthèse proposée : 1) ouverture du dossier et vérification des documents, 2) réservation auprès du "
     "transporteur, 3) préparation des documents douaniers, 4) suivi jusqu'à la livraison."),
]
_DEFAULT = ("Voici une réponse de démonstration. En mode réel, le modèle sélectionné par la passerelle "
            "répondrait ici à votre question, avec les mêmes règles de classification et de routage.")


class MockProvider:
    def __init__(self, private: bool = False, rng: random.Random | None = None):
        self.private = private
        self.rng = rng or random.Random()

    def complete(self, model: LlmModel, messages: list[dict]) -> ProviderResult:
        settings = get_settings()
        if model.litellm_name in settings.failing_models:
            raise ProviderError(f"Fournisseur simulé indisponible pour {model.litellm_name}")
        delay_ms = self.rng.randint(settings.mock_latency_min_ms, max(settings.mock_latency_min_ms, settings.mock_latency_max_ms))
        time.sleep(delay_ms / 1000)

        last_user = normalize(next((m["content"] for m in reversed(messages) if m["role"] == "user"), ""))
        body = next((text for keys, text in _CANNED if any(re.search(rf"\b{re.escape(k)}\b", last_user) for k in keys)),
                    _DEFAULT)
        where = "modèle privé simulé (Ollama non joignable)" if self.private else f"{model.display_name} simulé"
        text = f"[Réponse simulée - {where}] {body}"
        prompt_chars = sum(len(m["content"]) for m in messages)
        return ProviderResult(
            text=text,
            input_tokens=max(1, prompt_chars // 4),
            output_tokens=estimate_tokens(text),
            tokens_estimated=True,
            simulated=True,
            backend="mock-private" if self.private else "mock",
        )
