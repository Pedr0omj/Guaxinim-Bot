"""
elementos.py — Guaxinim Bot
Tabela de fraquezas/resistências por elemento, plano Paranormal (Secundário)
e aplicação de debuffs por elemento.
"""

import unicodedata

from config import ELEMENTS, DEBUFFS

# ─────────────────────────────────────────
# TABELA ELEMENTAL — PLANO PRINCIPAL
# ─────────────────────────────────────────
# Fraqueza simples: A > B  →  +8% dano
# Resistência inversa:  B > A  →  -25% (resistência natural)
# Mesmo elemento contra mesmo: +15% (afinidade natural)
# Custo Gnose via PA: +8 por ataque
# Esgotada? Penalidade 0.5× no dano

# Estrutura: WEAKNESSES[atacante] = [lista de elementos que são derrotados (+8%)]
WEAKNESSES: dict[str, list[str]] = {
    "Fogo": ["Vento", "Gelo"],
    "Gelo": ["Raio", "Fisico"],
    "Raio": ["Vento", "Gelo"],
    "Vento": ["Quantum", "Fisico"],
    "Quantum": ["Imaginario", "Raio"],
    "Imaginario": ["Fogo", "Quantum"],
    "Fisico": ["Raio", "Vento"],   # físico não tem ponto fraco mas penetra barreiras
}

RESISTANCES: dict[str, list[str]] = {
    "Fogo": ["Gelo"],
    "Gelo": ["Fogo"],
    "Raio": ["Gelo"],
    "Vento": ["Fogo"],
    "Quantum": ["Vento"],
    "Imaginario": ["Quantum"],
    "Fisico": [],
}

WEAKNESS_BONUS = 0.08   # +8% damage
AFFINITY_BONUS = 0.15   # same element
RESISTANCE_PENALTY = -0.25   # -25% damage


# ─────────────────────────────────────────
# PARANORMAL PLANE (Secondary)
# Variants amplify the base element (+20%)
# ─────────────────────────────────────────
PARANORMAL_PLANE: dict[str, dict] = {
    "Morte":          {"base": "Imaginario", "bonus_amp": 0.20, "emoji": "💀"},
    "Conhecimento":   {"base": "Quantum",    "bonus_amp": 0.20, "emoji": "📚"},
    "Sangue":         {"base": "Fogo",       "bonus_amp": 0.20, "emoji": "🩸"},
    "Energia":        {"base": "Raio",       "bonus_amp": 0.20, "emoji": "⚡"},
    "Corrupcao":      {"base": "Quantum",    "bonus_amp": 0.20, "emoji": "🟣"},
    "Astral":         {"base": "Imaginario", "bonus_amp": 0.20, "emoji": "🌌"},
    "Sagrado":        {"base": "Vento",      "bonus_amp": 0.20, "emoji": "✨"},
    "Abismo":         {"base": "Gelo",       "bonus_amp": 0.20, "emoji": "🕳️"},
    "Tempestade":     {"base": "Raio",       "bonus_amp": 0.20, "emoji": "🌩️"},
    "Medo":          {"base": "Fisico",     "bonus_amp": 0.20, "emoji": "😱"},
    "Reliquias":      {"base": "Imaginario", "bonus_amp": 0.20, "emoji": "🏺"},
    "Maldição":       {"base": "Quantum",    "bonus_amp": 0.20, "emoji": "🔱"},
}

# Simpler stats for Secondary (no Gnosis)
STATS_SECONDARY_SIMPLE = True   # flag for engine.py to ignore Gnosis in Secondaries


# ─────────────────────────────────────────
# DEBUFFS BY ELEMENT
# ─────────────────────────────────────────
# Mapping: element → debuff that can be applied on hit
DEBUFFS_BY_ELEMENT: dict[str, str | None] = {
    "Fogo":       "Queimadura",
    "Gelo":       "Congelado",
    "Raio":       "Atordoado",
    "Vento":      "Lentidao",
    "Quantum":    "Corrosao",
    "Imaginario": None,   # Imaginary uses narrative effects (Master defines)
    "Fisico":     "Sangramento",
}

# Base chance to apply debuff (can be modified by SEN)
BASE_DEBUFF_CHANCE = 0.30   # 30%


# ─────────────────────────────────────────
# FUNÇÕES UTILITÁRIAS
# ─────────────────────────────────────────

def normalizar_elemento(nome: str) -> str | None:
    """Return the canonical name of the element from alias or direct name."""
    nome_lower = nome.lower().strip()
    for elem, dados in ELEMENTS.items():
        if nome_lower == elem.lower() or nome_lower in dados["aliases"]:
            return elem
    return None


def calcular_bonus_elemental(elem_atacante: str, elem_alvo: str) -> float:
    """
    Return the elemental bonus/penalty multiplier.
    1.0 = neutral, 1.08 = weakness, 0.75 = resistance, 1.15 = affinity.
    """
    if elem_atacante == elem_alvo:
        return 1.0 + AFFINITY_BONUS

    if elem_alvo in WEAKNESSES.get(elem_atacante, []):
        return 1.0 + WEAKNESS_BONUS

    if elem_alvo in RESISTANCES.get(elem_atacante, []):
        return 1.0 + RESISTANCE_PENALTY

    return 1.0   # neutral


def get_variante_paranormal(nome: str) -> dict | None:
    """Return the Paranormal Plane data for a variant, or None."""
    # ADICIONADO: Eu normalizei nomes com/sem acento para aceitar entradas como
    # "Maldicao" e "Maldição" sem quebrar o cadastro do plano paranormal.
    def _normalizar(texto: str) -> str:
        texto = unicodedata.normalize("NFD", texto)
        texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
        return texto.lower().strip()

    nome_norm = _normalizar(nome)
    for variante, dados in PARANORMAL_PLANE.items():
        if nome_norm == _normalizar(variante):
            return {**dados, "nome": variante}
    return None


def get_debuff_elemento(elemento: str) -> dict | None:
    """Return the debuff data associated with the element, or None."""
    nome_debuff = DEBUFFS_BY_ELEMENT.get(elemento)
    if nome_debuff and nome_debuff in DEBUFFS:
        return {**DEBUFFS[nome_debuff], "nome": nome_debuff}
    return None


def get_cor_elemento(elemento: str) -> int:
    """Return the hex color of the element for use in Discord embedds."""
    return ELEMENTS.get(elemento, {}).get("color", 0x95A5A6)


def get_emoji_elemento(elemento: str) -> str:
    """Return the emoji of the element."""
    # Check paranormal plane first
    variante = get_variante_paranormal(elemento)
    if variante:
        return variante["emoji"]
    return ELEMENTS.get(elemento, {}).get("emoji", "⚔️")
