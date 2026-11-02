"""Données de référence de démonstration. TOUTES FICTIVES.

Les prix sont fictifs (is_demo=True) et les niveaux max des modèles sont des
hypothèses à valider avec la DSI (voir docs/DECISIONS.md).
"""
ALL_ROLES = ["ADMIN", "MANAGER", "DEVELOPER", "USER"]
PRIVILEGED = ["ADMIN", "MANAGER", "DEVELOPER"]

# (nom, budget mensuel €, limite tokens, plafond manager €)
DEPARTMENTS = [
    ("Transport maritime", 120, None, 15),
    ("Transport aérien", 90, None, 15),
    ("Douane", 100, None, 15),
    ("Finance", 60, None, 10),
    ("Informatique", 150, None, 30),
    ("Logistique", 80, None, 15),
    ("Direction", 60, None, 20),
]

DEMO_ACCOUNTS = [
    {"email": "admin@rdt-demo.local", "password": "Admin!2026", "role": "ADMIN", "full_name": "Claire Admin",
     "department": "Informatique", "budget": 30, "label": "Administrateur DSI"},
    {"email": "manager@rdt-demo.local", "password": "Manager!2026", "role": "MANAGER", "full_name": "Marc Manager",
     "department": "Transport maritime", "budget": 15, "label": "Manager Transport maritime"},
    {"email": "dev@rdt-demo.local", "password": "Dev!2026", "role": "DEVELOPER", "full_name": "Dina Développeuse",
     "department": "Informatique", "budget": 15, "label": "Développeuse"},
    {"email": "user@rdt-demo.local", "password": "User!2026", "role": "USER", "full_name": "Ulysse Utilisateur",
     "department": "Douane", "budget": 3, "label": "Utilisateur Douane (quota à 91 %)"},
    {"email": "quota@rdt-demo.local", "password": "Quota!2026", "role": "USER", "full_name": "Quentin Quota",
     "department": "Logistique", "budget": 2, "label": "Utilisateur Logistique (quota atteint)"},
]

FIRST_NAMES = ["Sophie", "Thomas", "Nadia", "Julien", "Camille", "Karim", "Élodie", "Antoine", "Inès", "Romain",
               "Léa", "Mehdi", "Pauline", "Hugo", "Sarah", "Nicolas", "Amina", "Baptiste", "Chloé", "Yanis",
               "Manon", "Lucas", "Fatima", "Maxime", "Laura", "Olivier", "Jade", "Samir", "Emma", "Vincent",
               "Anaïs", "Florian", "Leïla", "Damien", "Margaux"]
LAST_NAMES = ["Martin", "Bernard", "Moreau", "Laurent", "Garcia", "Roux", "Fournier", "Girard", "Bonnet", "Dupont",
              "Lambert", "Fontaine", "Rousseau", "Vincent", "Muller", "Lefèvre", "Faure", "André", "Mercier",
              "Blanc", "Guerin", "Boyer", "Garnier", "Chevalier", "Francois", "Legrand", "Gauthier", "Perrin",
              "Robin", "Clément", "Morin", "Nicolas", "Henry", "Roussel", "Mathieu"]

PROVIDERS = [
    ("OpenAI", "openai", "OPENAI_API_KEY"),
    ("Anthropic", "anthropic", "ANTHROPIC_API_KEY"),
    ("DeepSeek", "deepseek", "DEEPSEEK_API_KEY"),
    ("Google Gemini", "gemini", "GEMINI_API_KEY"),
    ("Ollama (interne)", "ollama", None),
]

# (fournisseur, nom affiché, nom LiteLLM, hébergement, niveau max, tier, rôles, prix entrée, prix sortie)
# Prix en € par million de tokens : FICTIFS. Prix Ollama = coût d'infrastructure interne estimé.
# Gemini Flash (offre gratuite Google AI Studio) : niveau max PUBLIC, car les données de l'offre
# gratuite peuvent être utilisées par Google pour améliorer ses produits.
MODELS = [
    ("Google Gemini", "Gemini 2.5 Flash (gratuit)", "gemini/gemini-2.5-flash", "EXTERNAL", "PUBLIC", "eco", ALL_ROLES,
     0.0, 0.0),
    ("DeepSeek", "DeepSeek Chat", "deepseek/deepseek-chat", "EXTERNAL", "PUBLIC", "eco", ALL_ROLES, 0.14, 0.28),
    ("OpenAI", "GPT-4.1 mini", "openai/gpt-4.1-mini", "EXTERNAL", "INTERNAL", "eco", ALL_ROLES, 0.40, 1.60),
    ("OpenAI", "GPT-4.1", "openai/gpt-4.1", "EXTERNAL", "INTERNAL", "premium", PRIVILEGED, 2.00, 8.00),
    ("Anthropic", "Claude Haiku 4.5", "anthropic/claude-haiku-4-5", "EXTERNAL", "INTERNAL", "standard", ALL_ROLES, 1.00, 5.00),
    ("Anthropic", "Claude Sonnet 4.5", "anthropic/claude-sonnet-4-5", "EXTERNAL", "INTERNAL", "premium", PRIVILEGED, 3.00, 15.00),
    ("Ollama (interne)", "Llama 3.1 8B (local)", "ollama/llama3.1:8b", "PRIVATE", "CONFIDENTIAL", "eco", ALL_ROLES, 0.25, 0.25),
    ("Ollama (interne)", "Qwen 2.5 14B (local)", "ollama/qwen2.5:14b", "PRIVATE", "CONFIDENTIAL", "standard",
     ALL_ROLES, 0.50, 0.50),
    # Sans prix : démontre l'affichage "coût non disponible".
    ("Ollama (interne)", "Mistral Nemo (local)", "ollama/mistral-nemo", "PRIVATE", "CONFIDENTIAL", "eco", PRIVILEGED, None, None),
]

# Lexique métier : (terme, catégorie, niveau, regex ?). Les regex s'appliquent sur un texte
# en minuscules et sans accents.
LEXICON = [
    (r"tarifs? negocies?", "commercial", "CONFIDENTIAL", True),
    ("contrat cadre", "commercial", "CONFIDENTIAL", False),
    (r"marges?", "commercial", "CONFIDENTIAL", True),
    ("cotation client", "commercial", "CONFIDENTIAL", False),
    ("grille tarifaire", "commercial", "CONFIDENTIAL", False),
    ("remise client", "commercial", "CONFIDENTIAL", False),
    ("Groupe Valmer", "client", "CONFIDENTIAL", False),
    ("Atlantis Retail", "client", "CONFIDENTIAL", False),
    ("NordAgro", "client", "CONFIDENTIAL", False),
    ("Textiles Orsini", "client", "CONFIDENTIAL", False),
    ("Médilog Santé", "client", "CONFIDENTIAL", False),
    (r"procedures? internes?", "procedure", "INTERNAL", True),
    ("note interne", "procedure", "INTERNAL", False),
    (r"\b(site|agence|entrepot|plateforme)s? (de |d'|du )?(fos|roissy|le havre|lyon|marseille|lille|strasbourg|rungis)\b",
     "site", "INTERNAL", True),
    (r"\brdt-\d{4}-\d{5}\b", "internal_id", "INTERNAL", True),   # numéro de dossier interne
    (r"\bcli-\d{5}\b", "internal_id", "INTERNAL", True),          # code client interne
]
