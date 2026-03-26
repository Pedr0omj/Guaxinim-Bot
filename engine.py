"""
engine.py — Guaxinim Bot
Fórmula de dano completa: Base + ATK + VA + Elem + Crit + RNG + Zona - DEF - VIT
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass

from config import (
    BASE_DANO, MULT_ATK, MULT_VA, MULT_ELEM,
    CRIT_CHANCE, CRIT_BONUS_MULT,
    DEF_FORMULA, VIT_FORMULA,
    ZONAS,
)
from elementos import calcular_bonus_elemental, get_variante_paranormal
from ficha import FichaPersonagem


# ─────────────────────────────────────────
# RESULTADO DE ATAQUE
# ─────────────────────────────────────────

@dataclass
class ResultadoAtaque:
    # Dados brutos
    atacante: str
    alvo: str
    acao: str              # texto da ação descrita pelo jogador

    # Dano
    dano_base: int
    dano_final: int
    dano_bloqueado: int    # absorvido por DEF + VIT
    dano_real: int         # dano efetivamente aplicado no HP

    # Flags
    e_critico: bool
    e_combo: bool          # combo com outro jogador (+30% dano extra)
    gnose_esgotada_antes: bool   # Gnose já estava zerada antes deste ataque

    # Elemental
    elemento: str
    bonus_elemental: float  # multiplicador (ex: 1.08)
    debuff_aplicado: str | None

    # Extras
    rng_valor: int          # valor do dado (1-20)
    zona: int
    hp_restante_alvo: int
    gnose_restante: int

    # Detalhes de cálculo (para embed)
    breakdown: dict         # dicionário com cada etapa do cálculo


# ─────────────────────────────────────────
# ENGINE PRINCIPAL
# ─────────────────────────────────────────

class CombatEngine:

    # ── ATAQUE PRINCIPAL ────────────────
    @staticmethod
    def calcular_ataque(
        atacante: FichaPersonagem,
        alvo: FichaPersonagem,
        acao: str,
        custo_gnose: int = 8,
        e_combo: bool = False,
        parceiro_combo: FichaPersonagem | None = None,
    ) -> ResultadoAtaque:
        """
        Executa um ataque completo e retorna o ResultadoAtaque.
        Não aplica dano ao alvo — isso é feito em main.py após confirmação do Mestre.
        """

        # ── 1. GNOSE ────────────────────
        gnose_esgotada_antes = atacante.gnose_esgotada
        if not gnose_esgotada_antes and not atacante.is_secundario:
            sucesso_gnose = atacante.gastar_gnose(custo_gnose)
            penalidade_gnose = 0.5 if not sucesso_gnose else 1.0
        else:
            penalidade_gnose = 0.5 if gnose_esgotada_antes else 1.0

        # ── 2. RNG (d20) ─────────────────
        rng = random.randint(1, 20)
        # RNG vira bônus de dano: (rng / 20) * 20  →  0 a 20 pontos extras
        rng_bonus = int((rng / 20) * 20)

        # ── 3. BASE + ATK ────────────────
        str_efetivo = CombatEngine._stat_com_debuff(atacante, "STR")
        atk_component = MULT_ATK * math.log(max(str_efetivo, 1)) * 10  # escala log
        base_component = BASE_DANO

        # ── 4. VANTAGEM DE AÇÃO (VA) ─────
        # VA = qualidade narrativa da ação (0-10, definida pela IA/Mestre)
        # Por padrão = AGI do atacante como proxy; Mestre pode sobrescrever
        agi_efetivo = CombatEngine._stat_com_debuff(atacante, "AGI")
        va = min(10, max(0, agi_efetivo // 3))   # 0-10
        va_component = MULT_VA * va * 5

        # ── 5. ELEMENTO ──────────────────
        elem_atacante = atacante.elemento_main
        elem_alvo     = alvo.elemento_main

        # Verifica se atacante tem Paranormal que amplifica
        bonus_paranormal = 0.0
        variante = get_variante_paranormal(atacante.elemento_secundario or "")
        if variante:
            bonus_paranormal = variante["bonus_amp"]   # +20%

        mult_elem = calcular_bonus_elemental(elem_atacante, elem_alvo)
        mult_elem += bonus_paranormal

        elem_component = MULT_ELEM * (mult_elem - 1.0) * 100  # converte para pontos

        # ── 6. SOMA PRÉ-CRIT ─────────────
        dano_pre_crit = (
            base_component
            + atk_component
            + va_component
            + elem_component
            + rng_bonus
        ) * penalidade_gnose

        # ── 7. CRÍTICO ───────────────────
        sen_efetivo = CombatEngine._stat_com_debuff(atacante, "SEN")
        crit_chance_real = CRIT_CHANCE + (sen_efetivo // 5)  # SEN aumenta crit chance
        e_critico = random.randint(1, 100) <= crit_chance_real

        dano_pos_crit = dano_pre_crit * (CRIT_BONUS_MULT if e_critico else 1.0)

        # ── 8. COMBO ─────────────────────
        # dano = (dano1 + dano2) * 1.3
        combo_bonus = 0
        if e_combo and parceiro_combo:
            str_parceiro = CombatEngine._stat_com_debuff(parceiro_combo, "STR")
            dano_parceiro = MULT_ATK * math.log(max(str_parceiro, 1)) * 10 + BASE_DANO * 0.5
            dano_pos_crit = (dano_pos_crit + dano_parceiro) * 1.3
            combo_bonus = int(dano_pos_crit * 0.3)

        # ── 9. ZONA ──────────────────────
        zona = atacante.zona
        zona_mult = 1 + (zona - 1) * 0.25  # Zona 1 = 1.0×, Zona 4 = 1.75×
        dano_pos_zona = dano_pos_crit * zona_mult

        # ── 10. DEFESA ───────────────────
        res_alvo = CombatEngine._stat_com_debuff(alvo, "RES")
        vit_alvo = CombatEngine._stat_com_debuff(alvo, "VIT")

        def_mitiga = DEF_FORMULA(res_alvo)
        vit_mitiga = VIT_FORMULA(vit_alvo)
        total_mitiga = def_mitiga + vit_mitiga

        dano_final = max(1, int(dano_pos_zona - total_mitiga))
        dano_base  = int(dano_pos_zona)

        # ── 11. DEBUFF ───────────────────
        debuff_aplicado = CombatEngine._tentar_aplicar_debuff(
            atacante, alvo, elem_atacante
        )

        breakdown = {
            "base":           int(base_component),
            "atk_log":        int(atk_component),
            "va":             int(va_component),
            "elem":           int(elem_component),
            "rng":            rng_bonus,
            "penalidade_gnose": penalidade_gnose,
            "critico":        e_critico,
            "crit_mult":      CRIT_BONUS_MULT if e_critico else 1.0,
            "combo":          e_combo,
            "combo_bonus":    combo_bonus,
            "zona":           zona,
            "zona_mult":      zona_mult,
            "def_mitiga":     def_mitiga,
            "vit_mitiga":     vit_mitiga,
            "total_mitiga":   total_mitiga,
            "mult_elem":      round(mult_elem, 2),
        }

        return ResultadoAtaque(
            atacante=atacante.nome,
            alvo=alvo.nome,
            acao=acao,
            dano_base=dano_base,
            dano_final=dano_final,
            dano_bloqueado=int(total_mitiga),
            dano_real=0,   # preenchido em main.py após aplicar no HP
            e_critico=e_critico,
            e_combo=e_combo,
            gnose_esgotada_antes=gnose_esgotada_antes,
            elemento=elem_atacante,
            bonus_elemental=round(mult_elem, 2),
            debuff_aplicado=debuff_aplicado,
            rng_valor=rng,
            zona=zona,
            hp_restante_alvo=alvo.hp_atual,   # antes de aplicar dano
            gnose_restante=atacante.gnose_atual,
            breakdown=breakdown,
        )

    # ── DEFESA / ESQUIVA ────────────────
    @staticmethod
    def calcular_defesa(defensor: FichaPersonagem) -> dict:
        """
        Esquiva ativa: VA defesa = AGI do defensor.
        VA alta → reduz 50% dano.
        VA baixa → falha.
        Basicamente: chance de esquiva = AGI / (AGI + 20).
        """
        agi = CombatEngine._stat_com_debuff(defensor, "AGI")
        chance = agi / (agi + 20)
        sucesso = random.random() < chance
        return {
            "sucesso":   sucesso,
            "agi_usado": agi,
            "chance":    round(chance * 100, 1),
        }

    @staticmethod
    def calcular_escudo(defensor: FichaPersonagem, valor_escudo: int) -> int:
        """
        Escudo/barreira: absorve antes de tirar HP.
        Valor = INT do defensor * multiplicador.
        """
        int_efetivo = CombatEngine._stat_com_debuff(defensor, "INT")
        escudo = int_efetivo * valor_escudo
        return int(escudo)

    # ── DESCANSO / GNOSE ────────────────
    @staticmethod
    def descansar_gnose(personagem: FichaPersonagem) -> int:
        """Recupera Gnose conforme a regra: /descansar → recupera Gnose_max."""
        if personagem.is_secundario:
            return 0
        recuperado = personagem.gnose_max - personagem.gnose_atual
        personagem.gnose_atual = personagem.gnose_max
        return recuperado

    # ── UTILITÁRIOS ─────────────────────
    @staticmethod
    def _stat_com_debuff(personagem: FichaPersonagem, stat: str) -> int:
        """Retorna o valor do stat aplicando penalidades de debuffs ativos."""
        from config import DEBUFFS
        base = getattr(personagem, stat, 0)
        multiplicador = 1.0
        for debuff_ativo in personagem.debuffs:
            nome_debuff = debuff_ativo["nome"]
            if nome_debuff in DEBUFFS:
                pen = DEBUFFS[nome_debuff].get("stat_pen", {})
                if stat in pen:
                    multiplicador += pen[stat]   # já é negativo ex: -0.20
        return max(1, int(base * multiplicador))

    @staticmethod
    def _tentar_aplicar_debuff(
        atacante: FichaPersonagem,
        alvo: FichaPersonagem,
        elemento: str,
    ) -> str | None:
        """Tenta aplicar debuff elemental no alvo. Retorna nome do debuff ou None."""
        from elementos import get_debuff_elemento, CHANCE_DEBUFF_BASE
        from config import DEBUFFS

        debuff_info = get_debuff_elemento(elemento)
        if not debuff_info:
            return None

        # Chance aumenta com SEN do atacante
        sen = CombatEngine._stat_com_debuff(atacante, "SEN")
        chance = CHANCE_DEBUFF_BASE + (sen / 200)   # máx ~80% com SEN altíssimo

        if random.random() < chance:
            duracao = debuff_info.get("duracao", 2)
            alvo.adicionar_debuff(debuff_info["nome"], duracao)
            return debuff_info["nome"]

        return None
