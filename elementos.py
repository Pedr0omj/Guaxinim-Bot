"""
elementos.py — Guaxinim Bot
Tabela de fraquezas/resistências elementais, plano Paranormal (Secundário)
e aplicação de debuffs por elemento.
"""

from config import ELEMENTOS, DEBUFFS

# ─────────────────────────────────────────
# TABELA ELEMENTAL — PLANO MAIN
# ─────────────────────────────────────────
# Fraqueza simples: A > B  →  +8% dano
# Resistência inversa:  B > A  →  -25% (resistência natural)
# Mesmo elemento contra mesmo: +15% (afinidade natural)
# Custo de Gnose via PA: +8 por ataque
# Esgotou? Penalidade 0.5× ao dano

# Estrutura: FRAQUEZAS[atacante] = [lista de elementos que ele vence (+8%)]
FRAQUEZAS: dict[str, list[str]] = {
    "Fogo":       ["Vento", "Gelo"],
    "Gelo":       ["Raio", "Fisico"],
    "Raio":       ["Vento", "Gelo"],
    "Vento":      ["Quantum", "Fisico"],
    "Quantum":    ["Imaginario", "Raio"],
    "Imaginario": ["Fogo", "Quantum"],
    "Fisico":     ["Raio", "Vento"],   # físico sem fraqueza dura, mas penetra barreiras
}

RESISTENCIAS: dict[str, list[str]] = {
    "Fogo":       ["Gelo"],
    "Gelo":       ["Fogo"],
    "Raio":       ["Gelo"],
    "Vento":      ["Fogo"],
    "Quantum":    ["Vento"],
    "Imaginario": ["Quantum"],
    "Fisico":     [],
}

BONUS_FRAQUEZA    =  0.08   # +8% dano
BONUS_AFINIDADE   =  0.15   # mesmo elemento
PENALIDADE_RESIST = -0.25   # -25% dano


# ─────────────────────────────────────────
# PLANO PARANORMAL (Secundário)
# Variantes amplificam o elemento base (+20%)
# ─────────────────────────────────────────
PLANO_PARANORMAL: dict[str, dict] = {
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

# Stats mais simples para Secundários (sem Gnose)
STATS_SECUNDARIO_SIMPLES = True   # flag para engine.py ignorar Gnose em Secundários


# ─────────────────────────────────────────
# DEBUFFS POR ELEMENTO
# ─────────────────────────────────────────
# Mapeamento: elemento → debuff que pode aplicar ao acertar
DEBUFFS_POR_ELEMENTO: dict[str, str | None] = {
    "Fogo":       "Queimadura",
    "Gelo":       "Congelado",
    "Raio":       "Atordoado",
    "Vento":      "Lentidao",
    "Quantum":    "Corrosao",
    "Imaginario": None,   # Imaginário usa efeitos narrativos (Mestre define)
    "Fisico":     "Sangramento",
}

# Chance base de aplicar debuff (pode ser modificada por SEN)
CHANCE_DEBUFF_BASE = 0.30   # 30%


# ─────────────────────────────────────────
# FUNÇÕES UTILITÁRIAS
# ─────────────────────────────────────────

def normalizar_elemento(nome: str) -> str | None:
    """Retorna o nome canônico do elemento a partir de alias ou nome direto."""
    nome_lower = nome.lower().strip()
    for elem, dados in ELEMENTOS.items():
        if nome_lower == elem.lower() or nome_lower in dados["alias"]:
            return elem
    return None


def calcular_bonus_elemental(elem_atacante: str, elem_alvo: str) -> float:
    """
    Retorna o multiplicador de bônus/penalidade elemental.
    1.0 = neutro, 1.08 = fraqueza, 0.75 = resistência, 1.15 = afinidade.
    """
    if elem_atacante == elem_alvo:
        return 1.0 + BONUS_AFINIDADE

    if elem_alvo in FRAQUEZAS.get(elem_atacante, []):
        return 1.0 + BONUS_FRAQUEZA

    if elem_alvo in RESISTENCIAS.get(elem_atacante, []):
        return 1.0 + PENALIDADE_RESIST

    return 1.0   # neutro


def get_variante_paranormal(nome: str) -> dict | None:
    """Retorna os dados do Plano Paranormal para uma variante, ou None."""
    for variante, dados in PLANO_PARANORMAL.items():
        if nome.lower() == variante.lower():
            return {**dados, "nome": variante}
    return None


def get_debuff_elemento(elemento: str) -> dict | None:
    """Retorna os dados do debuff associado ao elemento, ou None."""
    nome_debuff = DEBUFFS_POR_ELEMENTO.get(elemento)
    if nome_debuff and nome_debuff in DEBUFFS:
        return {**DEBUFFS[nome_debuff], "nome": nome_debuff}
    return None


def get_cor_elemento(elemento: str) -> int:
    """Retorna a cor hex do elemento para uso em embeds Discord."""
    return ELEMENTOS.get(elemento, {}).get("cor", 0x95A5A6)


def get_emoji_elemento(elemento: str) -> str:
    """Retorna o emoji do elemento."""
    # Verifica plano paranormal primeiro
    variante = get_variante_paranormal(elemento)
    if variante:
        return variante["emoji"]
    return ELEMENTOS.get(elemento, {}).get("emoji", "⚔️")
