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
GUILD_ID = int(os.getenv("GUILD_ID", 0))  # servidor de teste (sincronização rápida)

# ─────────────────────────────────────────
# ELEMENTOS — cores em hex para embeds
# ─────────────────────────────────────────
ELEMENTS: dict[str, dict] = {
    "Imaginario": {
        "color": 0x9B59B6,  # roxo/violeta
        "emoji": "🌀",
        "aliases": ["imaginario", "imaginário", "imag"],
    },
    "Quantum": {
        "color": 0xE91E8C,  # rosa/magenta
        "emoji": "🔮",
        "aliases": ["quantum", "quant"],
    },
    "Raio": {
        "color": 0xF1C40F,  # amarelo elétrico
        "emoji": "⚡",
        "aliases": ["raio", "lightning"],
    },
    "Vento": {
        "color": 0x1ABC9C,  # verde-água/turquesa
        "emoji": "🌪️",
        "aliases": ["vento", "wind"],
    },
    "Gelo": {
        "color": 0x5DADE2,  # azul claro/ciano
        "emoji": "❄️",
        "aliases": ["gelo", "ice"],
    },
    "Fogo": {
        "color": 0xE74C3C,  # laranja/vermelho
        "emoji": "🔥",
        "aliases": ["fogo", "fire"],
    },
    "Fisico": {
        "color": 0x95A5A6,  # cinza/branco
        "emoji": "⚔️",
        "aliases": ["fisico", "físico", "phys"],
    },
}

# Cor especial para crítico (sobrescreve cor do elemento)
CRITICAL_COLOR = 0xFF4500  # laranja-vermelho intenso
DEPLETED_GNOSIS_COLOR = 0x8B0000  # vermelho escuro

# ─────────────────────────────────────────
# ZONAS DE PODER (escala de dano)
# ─────────────────────────────────────────
ZONES: dict[int, dict] = {
    1: {"name": "Human/Physical", "ceiling": 1},
    2: {"name": "Basic Powers", "ceiling": 2},
    3: {"name": "Advanced Abilities", "ceiling": 3},
    4: {"name": "Conceptual/Max", "ceiling": 4},
}

# ─────────────────────────────────────────
# STATS BASE DO SISTEMA
# ─────────────────────────────────────────
# Nomes canônicos dos atributos aceitos na ficha
VALID_STATS = ["STR", "RES", "AGI", "SEN", "VIT", "INT"]

# Gnose: pool de PA por combate
DEFAULT_MAX_GNOSIS = 100  # pode ser sobrescrito na ficha
# ADICIONADO: Eu defini um teto de segurança para evitar fichas com valores absurdos
# de Gnose Máxima (ex.: 100000), o que quebraria o balanceamento do sistema.
GNOSE_MAX_CAP = 10000
# ADICIONADO: Eu defini um teto suave para o buff de ATK da Gnose em faixas altas,
# para impedir crescimento descontrolado de dano quando status e Gnose estão muito altos.
GNOSE_ATK_BUFF_SOFT_CAP = 1.50  # +150% no multiplicador de ATK por efeito de Gnose

# ─────────────────────────────────────────
# MECÂNICAS DE COMBATE
# ─────────────────────────────────────────

BASE_DAMAGE = 50  # dano base fixo antes dos multiplicadores
ATK_MULTIPLIER = 2.0  # multiplicador direto de Força
VA_MULTIPLIER = 1.0  # valoriza mais a avaliação de criatividade da IA
ELEMENT_MULTIPLIER = 0.25
CRITICAL_CHANCE = 15
CRITICAL_BONUS_MULTIPLIER = 1.5

# RES mitiga: 1.2x da RES
# VIT mitiga: Apenas metade da VIT vira armadura pura
DEF_FORMULA = lambda res: int(res * 1.2)
VIT_FORMULA = lambda vit: int(vit * 0.5)
# Fórmula de dano principal (sem crítico, sem elemento):
# dano = (BASE + ATK_MULTIPLIER * Força + VA_MULTIPLIER * VA) * ELEMENT_MULTIPLIER * Zona - DEF - VIT
# engine.py implementa isso com RNG e camadas completas.

# ─────────────────────────────────────────
# DEBUFFS PADRÃO
# ─────────────────────────────────────────
DEBUFFS: dict[str, dict] = {
    "Sangramento": {
        "emoji": "🩸",
        "description": "Perde HP por turno (FOR -20%)",
        "stat_penalty": {"STR": -0.20},
        "duration": 3,
    },
    "Queimadura": {
        "emoji": "🔥",
        "description": "Dano de fogo por turno",
        "stat_penalty": {},
        "duration": 3,
    },
    "Congelado": {
        "emoji": "❄️",
        "description": "AGI reduzido 50%, chance de pular turno",
        "stat_penalty": {"AGI": -0.50},
        "duration": 2,
    },
    "Atordoado": {
        "emoji": "💫",
        "description": "Não pode agir no próximo turno",
        "stat_penalty": {},
        "duration": 1,
    },
    "Corrosao": {
        "emoji": "🟢",
        "description": "RES reduzido (Quântico)",
        "stat_penalty": {"RES": -0.25},
        "duration": 3,
    },
    "Lentidao": {
        "emoji": "🌀",
        "description": "AGI reduzido 30%",
        "stat_penalty": {"AGI": -0.30},
        "duration": 2,
    },
    "DefesaAtiva": {
        "emoji": "🛡️",
        # ADICIONADO: Debuff que representa defesa bem-sucedida. Reduz próximo dano em 50%
        # e é consumido (removido) após 1 turno. Aplicado quando defesa bem-sucedida em _processar_defesa().
        "description": "Próximo dano reduzido em 50% (defesa ativa)",
        "stat_penalty": {},
        "duration": 1,
    },
}

# ─────────────────────────────────────────
# RAID
# ─────────────────────────────────────────
HP_BAR_GREEN = 0.60  # acima de 60% → verde
HP_BAR_YELLOW = 0.30  # entre 30-60% → amarelo
# abaixo de 30% → vermelho

BASE_BOSS_TENACITY = 100  # HP da barra de tenacidade

# ─────────────────────────────────────────
# MENSAGENS UI / TEXTOS
# ─────────────────────────────────────────
ATTACK_TITLE_NORMAL = "⚔️ Ataque"
ATTACK_TITLE_CRITICAL = "💥 CRÍTICO!"
TITLE_GNOSIS_DEPLETED = "⚠️ Gnose Esgotada"
DEFAULT_FOOTER = "Guaxinim Bot • Sistema de Combate"
