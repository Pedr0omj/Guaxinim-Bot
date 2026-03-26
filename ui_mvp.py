"""
ui_mvp.py — Guaxinim Bot
Construtores de embeds Discord: ataque normal, crítico, Gnose esgotada,
painel de raid, ficha, status.
"""

from __future__ import annotations
import discord
from config import (
    COR_CRITICO, COR_GNOSE_ESGOTADA, FOOTER_PADRAO,
    TITULO_ATAQUE_NORMAL, TITULO_ATAQUE_CRITICO, TITULO_GNOSE_ESGOTADA,
    ELEMENTOS, HP_BARRA_VERDE, HP_BARRA_AMARELO,
)
from elementos import get_cor_elemento, get_emoji_elemento
from engine import ResultadoAtaque
from ficha import FichaPersonagem
from debuff import formatar_debuffs_embed


# ─────────────────────────────────────────
# BARRA DE HP (texto)
# ─────────────────────────────────────────

def barra_hp(atual: int, maximo: int, tamanho: int = 10) -> str:
    """Gera barra visual de HP. Ex: ████████░░ 80/100"""
    if maximo <= 0:
        return "░" * tamanho + " 0/0"
    pct = atual / maximo
    cheio = round(pct * tamanho)
    vazio = tamanho - cheio

    if pct > HP_BARRA_VERDE:
        bloco = "🟩"
    elif pct > HP_BARRA_AMARELO:
        bloco = "🟨"
    else:
        bloco = "🟥"

    return bloco * cheio + "⬛" * vazio + f" `{atual}/{maximo}`"


def barra_gnose(atual: int, maximo: int) -> str:
    """Barra de Gnose com ◆ e ◇."""
    if maximo <= 0:
        return "Sem Gnose"
    cheio = atual
    vazio = maximo - atual
    return "◆" * cheio + "◇" * vazio + f" `{atual}/{maximo}`"


# ─────────────────────────────────────────
# EMBED — ATAQUE NORMAL
# ─────────────────────────────────────────

def embed_ataque(resultado: ResultadoAtaque, ficha_alvo: FichaPersonagem) -> discord.Embed:
    """Embed padrão para um ataque normal."""
    cor = get_cor_elemento(resultado.elemento)
    emoji_elem = get_emoji_elemento(resultado.elemento)

    embed = discord.Embed(
        title=f"{emoji_elem} {TITULO_ATAQUE_NORMAL} — {resultado.atacante}",
        description=f"*{resultado.acao}*",
        color=cor,
    )

    # ── Linha separadora + Dano ──────────
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    mult_str = ""
    if resultado.bonus_elemental != 1.0:
        sinal = "▲" if resultado.bonus_elemental > 1.0 else "▼"
        mult_str = f"  {sinal} ×{resultado.bonus_elemental:.2f} elem"

    embed.add_field(
        name="💥 Dano",
        value=f"**{resultado.dano_final}**{mult_str}",
        inline=True,
    )
    embed.add_field(
        name="🎲 RNG",
        value=f"`{resultado.rng_valor}/20`",
        inline=True,
    )
    embed.add_field(
        name="🌀 Zona",
        value=f"`Zona {resultado.zona}`",
        inline=True,
    )

    # ── HP do alvo ──────────────────────
    hp_pos_dano = max(0, ficha_alvo.hp_atual - resultado.dano_final)
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(
        name=f"❤️ HP — {ficha_alvo.nome}",
        value=barra_hp(hp_pos_dano, ficha_alvo.hp_max),
        inline=False,
    )

    # ── Gnose do atacante ───────────────
    if resultado.gnose_restante >= 0:
        embed.add_field(
            name="✨ Gnose",
            value=barra_gnose(resultado.gnose_restante, 9),
            inline=True,
        )

    # ── Debuffs aplicados ───────────────
    if resultado.debuff_aplicado:
        from config import DEBUFFS
        emoji_db = DEBUFFS.get(resultado.debuff_aplicado, {}).get("emoji", "⚠️")
        embed.add_field(
            name="⚠️ Debuff aplicado",
            value=f"{emoji_db} **{resultado.debuff_aplicado}**",
            inline=True,
        )

    # ── Debuffs ativos no alvo ──────────
    debuffs_str = formatar_debuffs_embed(ficha_alvo)
    embed.add_field(
        name=f"🩻 Status — {ficha_alvo.nome}",
        value=debuffs_str,
        inline=False,
    )

    embed.set_footer(text=FOOTER_PADRAO)
    return embed


# ─────────────────────────────────────────
# EMBED — CRÍTICO
# ─────────────────────────────────────────

def embed_critico(resultado: ResultadoAtaque, ficha_alvo: FichaPersonagem) -> discord.Embed:
    """Embed especial para ataque crítico — cor e título diferentes."""
    emoji_elem = get_emoji_elemento(resultado.elemento)

    embed = discord.Embed(
        title=f"💥 {TITULO_ATAQUE_CRITICO} — {resultado.atacante}",
        description=f"✦ *{resultado.acao}* ✦",
        color=COR_CRITICO,
    )

    embed.add_field(name="\u200b", value="\u200b", inline=False)

    embed.add_field(
        name="💥 Dano CRÍTICO",
        value=f"**__{resultado.dano_final}__**  *(×{resultado.breakdown['crit_mult']:.1f})*",
        inline=True,
    )
    embed.add_field(
        name="🎲 RNG",
        value=f"`{resultado.rng_valor}/20` 🎯",
        inline=True,
    )
    embed.add_field(
        name=f"{emoji_elem} Elemento",
        value=resultado.elemento,
        inline=True,
    )

    hp_pos_dano = max(0, ficha_alvo.hp_atual - resultado.dano_final)
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(
        name=f"❤️ HP — {ficha_alvo.nome}",
        value=barra_hp(hp_pos_dano, ficha_alvo.hp_max),
        inline=False,
    )

    if resultado.debuff_aplicado:
        from config import DEBUFFS
        emoji_db = DEBUFFS.get(resultado.debuff_aplicado, {}).get("emoji", "⚠️")
        embed.add_field(
            name="⚠️ Debuff aplicado",
            value=f"{emoji_db} **{resultado.debuff_aplicado}**",
            inline=True,
        )

    debuffs_str = formatar_debuffs_embed(ficha_alvo)
    embed.add_field(
        name=f"🩻 Status — {ficha_alvo.nome}",
        value=debuffs_str,
        inline=False,
    )

    embed.set_footer(text=f"{FOOTER_PADRAO} • CRÍTICO")
    return embed


# ─────────────────────────────────────────
# EMBED — GNOSE ESGOTADA
# ─────────────────────────────────────────

def embed_gnose_esgotada(
    resultado: ResultadoAtaque,
    ficha_alvo: FichaPersonagem,
) -> discord.Embed:
    """Embed com aviso visual destacado de Gnose esgotada."""
    embed = discord.Embed(
        title=f"⚠️ {TITULO_GNOSE_ESGOTADA} — {resultado.atacante}",
        description=(
            f"*{resultado.acao}*\n\n"
            "```diff\n- GNOSE ESGOTADA: dano reduzido a 50%\n```"
        ),
        color=COR_GNOSE_ESGOTADA,
    )

    embed.add_field(
        name="💥 Dano (penalizado)",
        value=f"**{resultado.dano_final}**  *(×0.5 sem Gnose)*",
        inline=True,
    )
    embed.add_field(
        name="🎲 RNG",
        value=f"`{resultado.rng_valor}/20`",
        inline=True,
    )
    embed.add_field(
        name="✨ Gnose",
        value="◇◇◇◇◇◇◇◇◇ `0/9` ⚠️",
        inline=True,
    )

    hp_pos_dano = max(0, ficha_alvo.hp_atual - resultado.dano_final)
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(
        name=f"❤️ HP — {ficha_alvo.nome}",
        value=barra_hp(hp_pos_dano, ficha_alvo.hp_max),
        inline=False,
    )

    embed.add_field(
        name="💡 Dica",
        value="Use `/descansar` para recuperar sua Gnose.",
        inline=False,
    )

    embed.set_footer(text=f"{FOOTER_PADRAO} • Gnose Esgotada")
    return embed


# ─────────────────────────────────────────
# EMBED — PAINEL DE RAID
# ─────────────────────────────────────────

def embed_raid_painel(
    boss_nome: str,
    boss_hp: int,
    boss_hp_max: int,
    boss_tenacidade: int,
    boss_tenacidade_max: int,
    boss_zona: int,
    jogadores: list[dict],  # [{"ficha": FichaPersonagem, "agiu": bool}]
    turno: int,
    fala_boss: str = "",
) -> discord.Embed:
    """
    Painel de raid — exibe boss, HP, tenacidade, jogadores e turnos.
    jogadores: lista de dicts com chaves 'ficha' (FichaPersonagem) e 'agiu' (bool).
    """
    embed = discord.Embed(
        title=f"⚔️ RAID — {boss_nome}",
        description=f"*\"{fala_boss}\"*" if fala_boss else f"**Turno {turno}**",
        color=0xC0392B,
    )

    if fala_boss:
        embed.add_field(
            name=f"🎭 Turno {turno}",
            value="\u200b",
            inline=False,
        )

    # ── Boss HP ──────────────────────────
    embed.add_field(
        name="💀 HP do Boss",
        value=barra_hp(boss_hp, boss_hp_max, tamanho=12),
        inline=False,
    )

    # ── Tenacidade ──────────────────────
    ten_pct = boss_tenacidade / boss_tenacidade_max if boss_tenacidade_max > 0 else 0
    ten_cheio = round(ten_pct * 8)
    ten_barra = "🔷" * ten_cheio + "⬛" * (8 - ten_cheio)
    embed.add_field(
        name="🔷 Tenacidade",
        value=f"{ten_barra} `{boss_tenacidade}/{boss_tenacidade_max}`",
        inline=True,
    )
    embed.add_field(
        name="🌀 Zona",
        value=f"`Zona {boss_zona}`",
        inline=True,
    )

    embed.add_field(name="\u200b", value="\u200b", inline=False)

    # ── Jogadores ───────────────────────
    for entry in jogadores:
        ficha: FichaPersonagem = entry["ficha"]
        agiu: bool             = entry["agiu"]

        icone_turno = "✅" if agiu else "⏳"
        elem_emoji  = get_emoji_elemento(ficha.elemento_main)
        hp_str      = barra_hp(ficha.hp_atual, ficha.hp_max, tamanho=8)
        debuffs_str = formatar_debuffs_embed(ficha)

        campo_valor = f"{hp_str}\n{debuffs_str}"

        embed.add_field(
            name=f"{icone_turno} {elem_emoji} {ficha.nome}",
            value=campo_valor,
            inline=True,
        )

    embed.set_footer(text=f"{FOOTER_PADRAO} • Raid")
    return embed


# ─────────────────────────────────────────
# EMBED — FICHA DO PERSONAGEM
# ─────────────────────────────────────────

def embed_ficha(ficha: FichaPersonagem) -> discord.Embed:
    """Exibe a ficha completa de um personagem com layout otimizado e compacto."""
    cor = get_cor_elemento(ficha.elemento_main)
    emoji = get_emoji_elemento(ficha.elemento_main)

    plano_str = ficha.plano
    if ficha.elemento_secundario:
        plano_str += f" ({ficha.elemento_secundario})"

    # 1. Agrupando informações estáticas na descrição para economizar espaço
    descricao = f"**Plano:** {plano_str}  |  **Zona:** {ficha.zona}  |  **Rebirths:** {ficha.rebirths}"

    embed = discord.Embed(
        title=f"{emoji} {ficha.nome}",
        description=descricao,
        color=cor,
    )

    # 2. Barras de HP e Gnose empilhadas no topo
    embed.add_field(
        name="❤️ HP",
        value=barra_hp(ficha.hp_atual, ficha.hp_max, tamanho=12),
        inline=False,
    )

    if not ficha.is_secundario:
        embed.add_field(
            name="✨ Gnose",
            value=barra_gnose(ficha.gnose_atual, ficha.gnose_max),
            inline=False,
        )

    # 3. Status agrupados
    stats_ofensiva = (
        f"**STR** `{ficha.STR}`\n"
        f"**RES** `{ficha.RES}`\n"
        f"**AGI** `{ficha.AGI}`"
    )
    stats_defensiva = (
        f"**SEN** `{ficha.SEN}`\n"
        f"**VIT** `{ficha.VIT}`\n"
        f"**INT** `{ficha.INT}`"
    )

    embed.add_field(name="🗡️ Ofensiva", value=stats_ofensiva, inline=True)
    embed.add_field(name="🛡️ Defensiva", value=stats_defensiva, inline=True)

    # Truque de formatação: Este campo invisível força a grade a se dividir em três partes.
    # Isso empurra as colunas de Ofensiva e Defensiva mais para perto uma da outra à esquerda.
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    # 4. Rodapé de Status e Tupper
    embed.add_field(
        name="🩻 Status Ativos",
        value=formatar_debuffs_embed(ficha),
        inline=True,
    )

    embed.add_field(
        name="🎮 Tupper",
        value=f"`{ficha.tupper_name}`",
        inline=True,
    )

    embed.set_footer(text=FOOTER_PADRAO)
    return embed


# ─────────────────────────────────────────
# SELETOR DE EMBED (dispatch)
# ─────────────────────────────────────────

def build_embed_ataque(
    resultado: ResultadoAtaque,
    ficha_alvo: FichaPersonagem,
) -> discord.Embed:
    """Escolhe automaticamente o embed correto com base no resultado."""
    if resultado.e_critico:
        return embed_critico(resultado, ficha_alvo)
    if resultado.gnose_esgotada_antes:
        return embed_gnose_esgotada(resultado, ficha_alvo)
    return embed_ataque(resultado, ficha_alvo)
