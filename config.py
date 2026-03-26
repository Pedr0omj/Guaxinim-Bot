"""
config.py — Guaxinim Bot
Constantes globais, elementos, cores e configurações gerais.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# TOKEN E IDs
# ─────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GUILD_ID   = int(os.getenv("GUILD_ID", 0))  # servidor de teste (sync rápido)

# ─────────────────────────────────────────
# ELEMENTOS — cores em hex para embeds
# ─────────────────────────────────────────
ELEMENTOS: dict[str, dict] = {
    "Imaginario": {
        "cor":    0x9B59B6,   # roxo/violeta
        "emoji":  "🌀",
        "alias":  ["imaginario", "imaginário", "imag"],
    },
    "Quantum": {
        "cor":    0xE91E8C,   # rosa/magenta
        "emoji":  "🔮",
        "alias":  ["quantum", "quant"],
    },
    "Raio": {
        "cor":    0xF1C40F,   # amarelo elétrico
        "emoji":  "⚡",
        "alias":  ["raio", "lightning"],
    },
    "Vento": {
        "cor":    0x1ABC9C,   # verde-água/turquesa
        "emoji":  "🌪️",
        "alias":  ["vento", "wind"],
    },
    "Gelo": {
        "cor":    0x5DADE2,   # azul claro/ciano
        "emoji":  "❄️",
        "alias":  ["gelo", "ice"],
    },
    "Fogo": {
        "cor":    0xE74C3C,   # laranja/vermelho
        "emoji":  "🔥",
        "alias":  ["fogo", "fire"],
    },
    "Fisico": {
        "cor":    0x95A5A6,   # cinza/branco
        "emoji":  "⚔️",
        "alias":  ["fisico", "físico", "phys"],
    },
}

# Cor especial para crítico (sobrescreve cor do elemento)
COR_CRITICO    = 0xFF4500   # laranja-vermelho intenso
COR_GNOSE_ESGOTADA = 0x8B0000  # vermelho escuro

# ─────────────────────────────────────────
# ZONAS DE PODER (escala de dano)
# ─────────────────────────────────────────
ZONAS: dict[int, dict] = {
    1: {"nome": "Humano/Físico",          "teto": 1},
    2: {"nome": "Poderes Básicos",         "teto": 2},
    3: {"nome": "Habilidades Avançadas",   "teto": 3},
    4: {"nome": "Conceitual/Max",          "teto": 4},
}

# ─────────────────────────────────────────
# STATS BASE DO SISTEMA
# ─────────────────────────────────────────
# Nomes canônicos dos atributos aceitos na ficha
STATS_VALIDOS = ["STR", "RES", "AGI", "SEN", "VIT", "INT"]

# Gnose: pool de PA por combate
GNOSE_MAX_PADRAO = 9  # pode ser sobrescrito na ficha

# ─────────────────────────────────────────
# MECÂNICAS DE COMBATE
# ─────────────────────────────────────────
BASE_DANO       = 50   # base fixa antes dos multiplicadores
MULT_ATK        = 0.6  # multiplicador do log(STR)
MULT_VA         = 0.6  # multiplicador da Vantagem de Ação (VA)
MULT_ELEM       = 0.25 # multiplicador do bônus elemental
CRIT_CHANCE     = 15   # % base de crítico
CRIT_BONUS_MULT = 1.5  # multiplicador de dano no crítico

# DEF mitiga: DEF = RES + 5 (secundários não têm RES, usam 0)
# VIT mitiga: VIT = camada secundária
DEF_FORMULA     = lambda res: res + 5
VIT_FORMULA     = lambda vit: vit

# Fórmula de dano principal (sem crítico, sem elemento):
# dano = (BASE + MULT_ATK * log(STR) + MULT_VA * VA) * MULT_ELEM_camadas * Zona - DEF - VIT
# A engine.py implementa isso com RNG e camadas completas.

# ─────────────────────────────────────────
# DEBUFFS PADRÃO
# ─────────────────────────────────────────
DEBUFFS: dict[str, dict] = {
    "Sangramento": {
        "emoji":    "🩸",
        "descricao": "Perde HP por turno (STR -20%)",
        "stat_pen":  {"STR": -0.20},
        "duracao":   3,
    },
    "Queimadura": {
        "emoji":    "🔥",
        "descricao": "Dano de fogo por turno",
        "stat_pen":  {},
        "duracao":   3,
    },
    "Congelado": {
        "emoji":    "❄️",
        "descricao": "AGI reduzida 50%, chance de skip",
        "stat_pen":  {"AGI": -0.50},
        "duracao":   2,
    },
    "Atordoado": {
        "emoji":    "💫",
        "descricao": "Não pode agir no próximo turno",
        "stat_pen":  {},
        "duracao":   1,
    },
    "Corrosao": {
        "emoji":    "🟢",
        "descricao": "RES reduzida (Quantum)",
        "stat_pen":  {"RES": -0.25},
        "duracao":   3,
    },
    "Lentidao": {
        "emoji":    "🌀",
        "descricao": "AGI reduzida 30%",
        "stat_pen":  {"AGI": -0.30},
        "duracao":   2,
    },
}

# ─────────────────────────────────────────
# RAID
# ─────────────────────────────────────────
HP_BARRA_VERDE   = 0.60   # acima de 60% → verde
HP_BARRA_AMARELO = 0.30   # entre 30-60% → amarelo
# abaixo de 30% → vermelho

TENACIDADE_BOSS_BASE = 100  # HP da barra de tenacidade

# ─────────────────────────────────────────
# MENSAGENS / TEXTOS UI
# ─────────────────────────────────────────
TITULO_ATAQUE_NORMAL  = "⚔️ Ataque"
TITULO_ATAQUE_CRITICO = "💥 CRÍTICO!"
TITULO_GNOSE_ESGOTADA = "⚠️ Gnose Esgotada"
FOOTER_PADRAO         = "Guaxinim Bot • Sistema de Combate"
