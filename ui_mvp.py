"""
ui_mvp.py — Guaxinim Bot
Resposta de combate: texto narrativo simples + 3 botões expansíveis.

Botão 1 — 👤 Status dos jogadores  (HP, Gnose, debuffs de atacante e alvo)
Botão 2 — 🧮 Detalhes do cálculo   (fórmula explicada passo a passo)
Botão 3 — 💀 Status do boss        (HP, zona, tenacidade — busca por nome do alvo)
"""

from __future__ import annotations
import discord
from config import (
    COR_CRITICO, COR_GNOSE_ESGOTADA, FOOTER_PADRAO,
    ELEMENTOS, HP_BARRA_VERDE, HP_BARRA_AMARELO,
)
from elementos import get_cor_elemento, get_emoji_elemento
from engine import ResultadoAtaque
from ficha import FichaPersonagem
from debuff import formatar_debuffs_embed


# ─────────────────────────────────────────
# BARRAS VISUAIS
# ─────────────────────────────────────────

def barra_hp(atual: int, maximo: int, tamanho: int = 10) -> str:
    if maximo <= 0:
        return "░" * tamanho + " 0/0"
    pct = atual / maximo
    cheio = round(pct * tamanho)
    vazio = tamanho - cheio
    bloco = "🟩" if pct > HP_BARRA_VERDE else ("🟨" if pct > HP_BARRA_AMARELO else "🟥")
    return bloco * cheio + "⬛" * vazio + f" `{atual}/{maximo}`"


def barra_gnose(atual: int, maximo: int) -> str:
    if maximo <= 0:
        return "Sem Gnose"
    return "◆" * atual + "◇" * (maximo - atual) + f" `{atual}/{maximo}`"


# ─────────────────────────────────────────
# TEXTO NARRATIVO PRINCIPAL (resposta simples)
# ─────────────────────────────────────────

def _montar_texto_ataque(
    resultado: ResultadoAtaque,
    ficha_alvo: FichaPersonagem,
    comentario_ia: str,
) -> str:
    """
    Texto limpo e narrativo enviado como mensagem principal.
    Sem embed — apenas markdown do Discord.
    """
    elem_emoji = get_emoji_elemento(resultado.elemento)
    nome_atk   = resultado.atacante
    nome_alvo  = resultado.alvo

    # Linha de abertura varia por tipo de resultado
    if resultado.e_critico:
        titulo = f"## 💥 CRÍTICO! — {nome_atk}"
    elif resultado.gnose_esgotada_antes:
        titulo = f"## ⚠️ {nome_atk} — Gnose Esgotada"
    else:
        titulo = f"## {elem_emoji} {nome_atk} ataca!"

    # Ação narrada
    linha_acao = f"> *{resultado.acao}*"

    # Resultado do dano
    if resultado.e_critico:
        linha_dano = (
            f"**{nome_atk}** desferiu um golpe devastador em **{nome_alvo}** "
            f"causando **__{resultado.dano_final}__ de dano** {elem_emoji} *(crítico!)*"
        )
    elif resultado.gnose_esgotada_antes:
        linha_dano = (
            f"**{nome_atk}** atacou **{nome_alvo}** com a Gnose esgotada, "
            f"causando **{resultado.dano_final} de dano** *(×0.5 — sem Gnose)*"
        )
    else:
        mult_str = ""
        if resultado.bonus_elemental > 1.05:
            mult_str = f" *(fraqueza elemental ▲)*"
        elif resultado.bonus_elemental < 0.95:
            mult_str = f" *(resistência elemental ▼)*"
        linha_dano = (
            f"**{nome_atk}** acertou **{nome_alvo}** causando "
            f"**{resultado.dano_final} de dano** {elem_emoji}{mult_str}"
        )

    # HP do alvo pós-dano
    hp_pct = ficha_alvo.hp_atual / ficha_alvo.hp_max if ficha_alvo.hp_max > 0 else 0
    if hp_pct <= 0:
        estado_hp = f"💀 **{nome_alvo}** está com `0 HP`!"
    elif hp_pct <= 0.30:
        estado_hp = f"❤️‍🔥 **{nome_alvo}** está em estado crítico: `{ficha_alvo.hp_atual}/{ficha_alvo.hp_max} HP`"
    elif hp_pct <= 0.60:
        estado_hp = f"🟨 **{nome_alvo}** perdeu bastante vida: `{ficha_alvo.hp_atual}/{ficha_alvo.hp_max} HP`"
    else:
        estado_hp = f"🟩 **{nome_alvo}** ainda está de pé: `{ficha_alvo.hp_atual}/{ficha_alvo.hp_max} HP`"

    # Debuff aplicado
    linha_debuff = ""
    if resultado.debuff_aplicado:
        from config import DEBUFFS
        emoji_db = DEBUFFS.get(resultado.debuff_aplicado, {}).get("emoji", "⚠️")
        linha_debuff = f"\n{emoji_db} **{nome_alvo}** ficou com **{resultado.debuff_aplicado}**!"

    # Comentário do Mestre IA
    linha_ia = f"\n🎭 *\"{comentario_ia}\"*" if comentario_ia else ""

    # Gnose esgotou neste turno → aviso
    linha_gnose_warn = ""
    if resultado.gnose_esgotada_antes and resultado.gnose_restante == 0:
        linha_gnose_warn = f"\n✨ Gnose de **{nome_atk}** esgotada — use `/descansar` para recuperar."

    return "\n".join(filter(None, [
        titulo,
        linha_acao,
        "",
        linha_dano,
        estado_hp,
        linha_debuff.strip() or None,
        linha_ia.strip() or None,
        linha_gnose_warn.strip() or None,
    ]))


# ─────────────────────────────────────────
# VIEW COM 3 BOTÕES
# ─────────────────────────────────────────

class AtaqueView(discord.ui.View):
    """
    View persistida por 5 minutos com 3 botões:
    1. 👤 Status dos jogadores
    2. 🧮 Detalhes do cálculo
    3. 💀 Status do boss/alvo
    """

    def __init__(
        self,
        resultado: ResultadoAtaque,
        ficha_alvo: FichaPersonagem,
        ficha_atacante: FichaPersonagem,
    ):
        super().__init__(timeout=300)
        self.resultado      = resultado
        self.ficha_alvo     = ficha_alvo
        self.ficha_atacante = ficha_atacante

    # ── Botão 1: Status dos jogadores ──
    @discord.ui.button(label="👤 Jogadores", style=discord.ButtonStyle.secondary)
    async def btn_jogadores(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = _embed_status_jogadores(self.resultado, self.ficha_alvo, self.ficha_atacante)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Botão 2: Detalhes do cálculo ───
    @discord.ui.button(label="🧮 Cálculo", style=discord.ButtonStyle.secondary)
    async def btn_calculo(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = _embed_detalhes_calculo(self.resultado)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Botão 3: Status do boss/alvo ───
    @discord.ui.button(label="💀 Boss", style=discord.ButtonStyle.secondary)
    async def btn_boss(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = _embed_status_boss(self.ficha_alvo)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_timeout(self):
        # Desabilita botões ao expirar
        for item in self.children:
            item.disabled = True


# ─────────────────────────────────────────
# EMBED — BOTÃO 1: STATUS DOS JOGADORES
# ─────────────────────────────────────────

def _embed_status_jogadores(
    resultado: ResultadoAtaque,
    ficha_alvo: FichaPersonagem,
    ficha_atacante: FichaPersonagem,
) -> discord.Embed:
    cor = get_cor_elemento(resultado.elemento)
    embed = discord.Embed(title="👤 Status dos Jogadores", color=cor)

    # ── Atacante ──
    atk_gnose = (
        barra_gnose(resultado.gnose_restante, ficha_atacante.gnose_max)
        if not ficha_atacante.is_secundario
        else "*Sem Gnose (Paranormal)*"
    )
    atk_debuffs = formatar_debuffs_embed(ficha_atacante)
    embed.add_field(
        name=f"{get_emoji_elemento(ficha_atacante.elemento_main)} {ficha_atacante.nome} *(atacante)*",
        value=(
            f"❤️ HP: {barra_hp(ficha_atacante.hp_atual, ficha_atacante.hp_max)}\n"
            f"✨ Gnose: {atk_gnose}\n"
            f"🩻 Debuffs: {atk_debuffs}"
        ),
        inline=False,
    )

    embed.add_field(name="\u200b", value="\u200b", inline=False)

    # ── Alvo ──
    alvo_debuffs = formatar_debuffs_embed(ficha_alvo)
    embed.add_field(
        name=f"{get_emoji_elemento(ficha_alvo.elemento_main)} {ficha_alvo.nome} *(alvo)*",
        value=(
            f"❤️ HP: {barra_hp(ficha_alvo.hp_atual, ficha_alvo.hp_max)}\n"
            f"🩻 Debuffs: {alvo_debuffs}"
        ),
        inline=False,
    )

    embed.set_footer(text=FOOTER_PADRAO)
    return embed


# ─────────────────────────────────────────
# EMBED — BOTÃO 2: DETALHES DO CÁLCULO
# ─────────────────────────────────────────

def _embed_detalhes_calculo(resultado: ResultadoAtaque) -> discord.Embed:
    bd = resultado.breakdown
    cor = COR_CRITICO if resultado.e_critico else get_cor_elemento(resultado.elemento)

    embed = discord.Embed(
        title="🧮 Detalhes do Cálculo",
        description=(
            f"Veja como o dano de **{resultado.dano_final}** foi calculado, "
            f"passo a passo:"
        ),
        color=cor,
    )

    # ── Passo 1: Componentes base ──
    embed.add_field(
        name="1️⃣ Componentes de Ataque",
        value=(
            f"```\n"
            f"Base fixo         = {bd['base']:>6}\n"
            f"ATK log(STR)      = {bd['atk_log']:>6}  (força bruta)\n"
            f"VA (qualid. ação) = {bd['va']:>6}  (avaliação do Mestre)\n"
            f"Bônus RNG d20     = {bd['rng']:>6}  (dado: {resultado.rng_valor}/20)\n"
            f"─────────────────────────\n"
            f"Subtotal          = {bd['base'] + bd['atk_log'] + bd['va'] + bd['rng']:>6}\n"
            f"```"
        ),
        inline=False,
    )

    # ── Passo 2: Modificadores ──
    penalidade_str = (
        "✅ Normal (×1.0)" if bd["penalidade_gnose"] == 1.0
        else "⚠️ Sem Gnose (×0.5)"
    )
    embed.add_field(
        name="2️⃣ Modificadores",
        value=(
            f"**Gnose:** {penalidade_str}\n"
            f"**Elemento {resultado.elemento}:** ×{bd['mult_elem']:.2f} "
            f"*(bônus elemental = +{bd['elem']} pts)*\n"
            f"**Zona {bd['zona']}:** ×{bd['zona_mult']:.2f}"
        ),
        inline=False,
    )

    # ── Passo 3: Crítico / Combo ──
    crit_str = f"💥 **SIM** — dano multiplicado por ×{bd['crit_mult']:.1f}" if bd["critico"] else "Não"
    combo_str = f"⚔️ **SIM** — bônus de +{bd['combo_bonus']}" if bd["combo"] else "Não"
    embed.add_field(
        name="3️⃣ Crítico & Combo",
        value=f"**Crítico:** {crit_str}\n**Combo:** {combo_str}",
        inline=False,
    )

    # ── Passo 4: Defesa e resultado final ──
    embed.add_field(
        name="4️⃣ Defesas do Alvo",
        value=(
            f"```\n"
            f"DEF (RES + 5)  = {bd['def_mitiga']:>6}  (mitiga dano físico)\n"
            f"VIT            = {bd['vit_mitiga']:>6}  (camada de vitalidade)\n"
            f"Total mitigado = {bd['total_mitiga']:>6}\n"
            f"```"
        ),
        inline=False,
    )

    embed.add_field(
        name="✅ Dano Final",
        value=(
            f"```\n"
            f"Dano bruto     = {resultado.dano_base:>6}\n"
            f"Mitigado       = {resultado.dano_bloqueado:>6}\n"
            f"──────────────────────\n"
            f"Dano aplicado  = {resultado.dano_final:>6}\n"
            f"```"
        ),
        inline=False,
    )

    embed.set_footer(text=f"{FOOTER_PADRAO} • Cálculo detalhado")
    return embed


# ─────────────────────────────────────────
# EMBED — BOTÃO 3: STATUS DO BOSS / ALVO
# ─────────────────────────────────────────

def _embed_status_boss(ficha_alvo: FichaPersonagem) -> discord.Embed:
    cor = get_cor_elemento(ficha_alvo.elemento_main)
    emoji = get_emoji_elemento(ficha_alvo.elemento_main)

    hp_pct = ficha_alvo.hp_atual / ficha_alvo.hp_max if ficha_alvo.hp_max > 0 else 0
    if hp_pct > HP_BARRA_VERDE:
        estado = "🟢 Saudável"
    elif hp_pct > HP_BARRA_AMARELO:
        estado = "🟡 Machucado"
    elif hp_pct > 0:
        estado = "🔴 Estado crítico"
    else:
        estado = "💀 Derrotado"

    embed = discord.Embed(
        title=f"{emoji} {ficha_alvo.nome}",
        description=f"**Estado:** {estado}",
        color=cor,
    )

    embed.add_field(
        name="❤️ HP",
        value=barra_hp(ficha_alvo.hp_atual, ficha_alvo.hp_max, tamanho=12),
        inline=False,
    )

    embed.add_field(
        name="📊 Stats",
        value=(
            f"STR `{ficha_alvo.STR}` · RES `{ficha_alvo.RES}` · "
            f"AGI `{ficha_alvo.AGI}` · VIT `{ficha_alvo.VIT}`"
        ),
        inline=False,
    )

    embed.add_field(
        name="🌀 Zona · Elemento",
        value=f"Zona `{ficha_alvo.zona}` · {emoji} {ficha_alvo.elemento_main}",
        inline=True,
    )

    debuffs_str = formatar_debuffs_embed(ficha_alvo)
    embed.add_field(
        name="🩻 Status Ativos",
        value=debuffs_str,
        inline=False,
    )

    embed.set_footer(text=f"{FOOTER_PADRAO} • Status do Boss/Alvo")
    return embed


# ─────────────────────────────────────────
# BUILDER PRINCIPAL — chamado em main.py
# ─────────────────────────────────────────

def build_mensagem_ataque(
    resultado: ResultadoAtaque,
    ficha_alvo: FichaPersonagem,
    ficha_atacante: FichaPersonagem,
    comentario_ia: str = "",
) -> tuple[str, AtaqueView]:
    """
    Retorna (texto, view) prontos para enviar como resposta de ataque.
    O texto é narrativo e limpo; a view contém os 3 botões de detalhes.
    """
    texto = _montar_texto_ataque(resultado, ficha_alvo, comentario_ia)
    view  = AtaqueView(resultado, ficha_alvo, ficha_atacante)
    return texto, view


# ─────────────────────────────────────────
# EMBEDS LEGADOS (usados em slash commands)
# ─────────────────────────────────────────

def embed_ficha(ficha: FichaPersonagem) -> discord.Embed:
    """Ficha completa do personagem para /ficha_ver e /status."""
    cor   = get_cor_elemento(ficha.elemento_main)
    emoji = get_emoji_elemento(ficha.elemento_main)
    plano_str = ficha.plano + (f" ({ficha.elemento_secundario})" if ficha.elemento_secundario else "")

    embed = discord.Embed(
        title=f"{emoji} {ficha.nome}",
        description=f"**Plano:** {plano_str}  |  **Zona:** {ficha.zona}  |  **Rebirths:** {ficha.rebirths}",
        color=cor,
    )

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

    embed.add_field(
        name="🗡️ Ofensiva",
        value=f"**STR** `{ficha.STR}`\n**RES** `{ficha.RES}`\n**AGI** `{ficha.AGI}`",
        inline=True,
    )
    embed.add_field(
        name="🛡️ Defensiva",
        value=f"**SEN** `{ficha.SEN}`\n**VIT** `{ficha.VIT}`\n**INT** `{ficha.INT}`",
        inline=True,
    )
    embed.add_field(name="\u200b", value="\u200b", inline=True)

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
# PAINEL DE RAID (mantido para uso futuro)
# ─────────────────────────────────────────

def embed_raid_painel(
    boss_nome: str,
    boss_hp: int,
    boss_hp_max: int,
    boss_tenacidade: int,
    boss_tenacidade_max: int,
    boss_zona: int,
    jogadores: list[dict],
    turno: int,
    fala_boss: str = "",
) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔️ RAID — {boss_nome}",
        description=f"*\"{fala_boss}\"*" if fala_boss else f"**Turno {turno}**",
        color=0xC0392B,
    )
    if fala_boss:
        embed.add_field(name=f"🎭 Turno {turno}", value="\u200b", inline=False)

    embed.add_field(
        name="💀 HP do Boss",
        value=barra_hp(boss_hp, boss_hp_max, tamanho=12),
        inline=False,
    )

    ten_pct   = boss_tenacidade / boss_tenacidade_max if boss_tenacidade_max > 0 else 0
    ten_cheio = round(ten_pct * 8)
    ten_barra = "🔷" * ten_cheio + "⬛" * (8 - ten_cheio)
    embed.add_field(
        name="🔷 Tenacidade",
        value=f"{ten_barra} `{boss_tenacidade}/{boss_tenacidade_max}`",
        inline=True,
    )
    embed.add_field(name="🌀 Zona", value=f"`Zona {boss_zona}`", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    for entry in jogadores:
        ficha: FichaPersonagem = entry["ficha"]
        agiu: bool = entry["agiu"]
        embed.add_field(
            name=f"{'✅' if agiu else '⏳'} {get_emoji_elemento(ficha.elemento_main)} {ficha.nome}",
            value=f"{barra_hp(ficha.hp_atual, ficha.hp_max, tamanho=8)}\n{formatar_debuffs_embed(ficha)}",
            inline=True,
        )

    embed.set_footer(text=f"{FOOTER_PADRAO} • Raid")
    return embed
