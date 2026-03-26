"""
ui_mvp.py — Guaxinim Bot
Resposta de combate: texto narrativo simples + 3 botões expansíveis.
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

def barra_gnose(atual: int, maximo: int, tamanho: int = 10) -> str:
    if maximo <= 0:
        return "Sem Gnose"
    pct = max(0.0, min(1.0, atual / maximo))
    cheio = round(pct * tamanho)
    vazio = tamanho - cheio
    return "🟦" * cheio + "⬛" * vazio + f" `{atual}/{maximo}`"

def barra_sp(atual: int, maximo: int) -> str:
    if maximo <= 0:
        return "Sem SP"
    atual_safe = max(0, atual)
    return "🌟" * atual_safe + "🌑" * max(0, (maximo - atual_safe)) + f" `{atual_safe}/{maximo}`"


# ─────────────────────────────────────────
# TEXTO NARRATIVO PRINCIPAL (resposta simples)
# ─────────────────────────────────────────

def _montar_texto_ataque(
    resultado: ResultadoAtaque,
    ficha_alvo: FichaPersonagem,
    comentario_ia: str,
) -> str:
    elem_emoji = get_emoji_elemento(resultado.elemento)
    nome_atk   = resultado.atacante
    nome_alvo  = resultado.alvo

    if resultado.e_critico:
        titulo = f"## 💥 CRÍTICO! — {nome_atk}"
    elif resultado.gnose_esgotada_antes:
        titulo = f"## ⚠️ {nome_atk} — Gnose Esgotada"
    else:
        titulo = f"## {elem_emoji} {nome_atk} ataca!"

    linha_acao = f"> *{resultado.acao}*"

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

    hp_pct = ficha_alvo.hp_atual / ficha_alvo.hp_max if ficha_alvo.hp_max > 0 else 0
    if hp_pct <= 0:
        estado_hp = f"💀 **{nome_alvo}** está com `0 HP`!"
    elif hp_pct <= 0.30:
        estado_hp = f"❤️‍🔥 **{nome_alvo}** está em estado crítico: `{ficha_alvo.hp_atual}/{ficha_alvo.hp_max} HP`"
    elif hp_pct <= 0.60:
        estado_hp = f"🟨 **{nome_alvo}** perdeu bastante vida: `{ficha_alvo.hp_atual}/{ficha_alvo.hp_max} HP`"
    else:
        estado_hp = f"🟩 **{nome_alvo}** ainda está de pé: `{ficha_alvo.hp_atual}/{ficha_alvo.hp_max} HP`"

    linha_debuff = ""
    if resultado.debuff_aplicado:
        from config import DEBUFFS
        emoji_db = DEBUFFS.get(resultado.debuff_aplicado, {}).get("emoji", "⚠️")
        linha_debuff = f"\n{emoji_db} **{nome_alvo}** ficou com **{resultado.debuff_aplicado}**!"

    linha_ia = f"\n🎭 *\"{comentario_ia}\"*" if comentario_ia else ""

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

    @discord.ui.button(label="👤 Jogadores", style=discord.ButtonStyle.secondary)
    async def btn_jogadores(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = _embed_status_jogadores(self.resultado, self.ficha_alvo, self.ficha_atacante)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🧮 Cálculo", style=discord.ButtonStyle.secondary)
    async def btn_calculo(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = _embed_detalhes_calculo(self.resultado)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="💀 Boss", style=discord.ButtonStyle.secondary)
    async def btn_boss(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = _embed_status_boss(self.ficha_alvo)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_timeout(self):
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

    if not ficha_atacante.is_secundario:
        atk_gnose = barra_gnose(resultado.gnose_restante, ficha_atacante.gnose_max)
        atk_sp = barra_sp(getattr(ficha_atacante, 'sp_atual', 0), getattr(ficha_atacante, 'sp_max', 10))
        status_energia = f"✨ Gnose: {atk_gnose}\n⭐ SP: {atk_sp}\n"
    else:
        status_energia = "*Sem Gnose/SP (Paranormal)*\n"

    atk_debuffs = formatar_debuffs_embed(ficha_atacante)
    embed.add_field(
        name=f"{get_emoji_elemento(ficha_atacante.elemento_main)} {ficha_atacante.nome} *(atacante)*",
        value=(
            f"❤️ HP: {barra_hp(ficha_atacante.hp_atual, ficha_atacante.hp_max)}\n"
            f"{status_energia}"
            f"🩻 Debuffs: {atk_debuffs}"
        ),
        inline=False,
    )

    embed.add_field(name="\u200b", value="\u200b", inline=False)

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
        description=(f"Veja como o dano de **{resultado.dano_final}** foi calculado, passo a passo:"),
        color=cor,
    )

    embed.add_field(
        name="1️⃣ Componentes de Ataque",
        value=(
            f"```\n"
            f"Base fixo         = {bd['base']:>6}\n"
            f"ATK (Força)       = {bd['atk_log']:>6}  (força bruta)\n"
            f"VA (qualid. ação) = {bd['va']:>6}  (avaliação do Mestre)\n"
            f"Bônus RNG d20     = {bd['rng']:>6}  (dado: {resultado.rng_valor}/20)\n"
            f"─────────────────────────\n"
            f"Subtotal          = {bd['base'] + bd['atk_log'] + bd['va'] + bd['rng']:>6}\n"
            f"```"
        ),
        inline=False,
    )

    penalidade_str = "✅ Normal (×1.0)" if bd["penalidade_gnose"] == 1.0 else "⚠️ Sem Gnose (×0.5)"
    embed.add_field(
        name="2️⃣ Modificadores",
        value=(
            f"**Gnose:** {penalidade_str}\n"
            f"**Elemento {resultado.elemento}:** ×{bd['mult_elem']:.2f} *(bônus elemental = +{bd['elem']} pts)*\n"
            f"**Zona {bd['zona']}:** ×{bd['zona_mult']:.2f}"
        ),
        inline=False,
    )

    crit_str = f"💥 **SIM** — dano multiplicado por ×{bd['crit_mult']:.1f}" if bd["critico"] else "Não"
    combo_str = f"⚔️ **SIM** — bônus de +{bd['combo_bonus']}" if bd["combo"] else "Não"
    embed.add_field(
        name="3️⃣ Crítico & Combo",
        value=f"**Crítico:** {crit_str}\n**Combo:** {combo_str}",
        inline=False,
    )

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
# BUILDER PRINCIPAL
# ─────────────────────────────────────────

def build_mensagem_ataque(
    resultado: ResultadoAtaque,
    ficha_alvo: FichaPersonagem,
    ficha_atacante: FichaPersonagem,
    comentario_ia: str = "",
) -> tuple[str, AtaqueView]:
    texto = _montar_texto_ataque(resultado, ficha_alvo, comentario_ia)
    view  = AtaqueView(resultado, ficha_alvo, ficha_atacante)
    return texto, view


# ─────────────────────────────────────────
# INTERFACE DE FICHA INTERATIVA
# ─────────────────────────────────────────

class FichaView(discord.ui.View):
    def __init__(self, ficha: FichaPersonagem, dono: discord.Member | discord.User | None = None):
        super().__init__(timeout=120)
        self.ficha = ficha
        self.dono = dono

    def _base_embed(self) -> discord.Embed:
        cor = get_cor_elemento(self.ficha.elemento_main)
        emoji = get_emoji_elemento(self.ficha.elemento_main)
        embed = discord.Embed(title=f"{emoji} {self.ficha.nome}", color=cor)
        
        if self.dono:
            embed.set_author(name=f"Jogador: {self.dono.display_name}", icon_url=self.dono.display_avatar.url)
        
        embed.set_footer(text=FOOTER_PADRAO)
        return embed

    @discord.ui.button(label="📄 Info Básica", style=discord.ButtonStyle.primary, custom_id="btn_geral")
    async def btn_geral(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self._base_embed()
        embed.description = "**Informações Gerais do Personagem**"
        
        plano_str = self.ficha.plano
        if self.ficha.elemento_secundario:
            plano_str += f" ({self.ficha.elemento_secundario})"
            
        embed.add_field(name="🌍 Plano de Existência", value=f"`{plano_str}`", inline=True)
        embed.add_field(name="🌀 Zona de Poder", value=f"`Zona {self.ficha.zona}`", inline=True)
        embed.add_field(name="🔄 Rebirths", value=f"`{self.ficha.rebirths}`", inline=True)
        embed.add_field(name="🎮 Tupper Registrado", value=f"`{self.ficha.tupper_name}`", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="❤️ Status e Vida", style=discord.ButtonStyle.success, custom_id="btn_status")
    async def btn_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self._base_embed()
        embed.description = "**Condição Atual de Combate**"
        
        embed.add_field(
            name="❤️ Pontos de Vida (HP)", 
            value=barra_hp(self.ficha.hp_atual, self.ficha.hp_max, tamanho=12), 
            inline=False
        )
        
        if not self.ficha.is_secundario:
            embed.add_field(
                name="✨ Energia (Gnose)", 
                value=barra_gnose(self.ficha.gnose_atual, self.ficha.gnose_max, tamanho=12), 
                inline=False
            )
            embed.add_field(
                name="⭐ Pontos de Perícia (SP)", 
                value=barra_sp(getattr(self.ficha, 'sp_atual', 0), getattr(self.ficha, 'sp_max', 10)), 
                inline=False
            )
            
        embed.add_field(name="🩻 Status Ativos", value=formatar_debuffs_embed(self.ficha), inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📊 Atributos", style=discord.ButtonStyle.secondary, custom_id="btn_atributos")
    async def btn_atributos(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self._base_embed()
        embed.description = "**Estatísticas e Capacidades**"
        
        embed.add_field(
            name="🗡️ Ofensiva",
            value=f"**STR** `{self.ficha.STR}`\n**RES** `{self.ficha.RES}`\n**AGI** `{self.ficha.AGI}`",
            inline=True,
        )
        embed.add_field(
            name="🛡️ Defensiva",
            value=f"**SEN** `{self.ficha.SEN}`\n**VIT** `{self.ficha.VIT}`\n**INT** `{self.ficha.INT}`",
            inline=True,
        )
        await interaction.response.edit_message(embed=embed, view=self)


def build_mensagem_ficha(ficha: FichaPersonagem, dono: discord.Member | discord.User | None = None) -> tuple[discord.Embed, discord.ui.View]:
    """Constrói a mensagem inicial da ficha (Aba de Info Básica)."""
    view = FichaView(ficha, dono)
    
    cor = get_cor_elemento(ficha.elemento_main)
    emoji = get_emoji_elemento(ficha.elemento_main)
    embed = discord.Embed(title=f"{emoji} {ficha.nome}", description="**Informações Gerais do Personagem**", color=cor)
    
    if dono:
        embed.set_author(name=f"Jogador: {dono.display_name}", icon_url=dono.display_avatar.url)
        
    plano_str = ficha.plano
    if ficha.elemento_secundario:
        plano_str += f" ({ficha.elemento_secundario})"
        
    embed.add_field(name="🌍 Plano de Existência", value=f"`{plano_str}`", inline=True)
    embed.add_field(name="🌀 Zona de Poder", value=f"`Zona {ficha.zona}`", inline=True)
    embed.add_field(name="🔄 Rebirths", value=f"`{ficha.rebirths}`", inline=True)
    embed.add_field(name="🎮 Tupper Registrado", value=f"`{ficha.tupper_name}`", inline=False)
    
    embed.set_footer(text=FOOTER_PADRAO)
    return embed, view

# ─────────────────────────────────────────
# PAINEL DE RAID E ULTIMATES
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

class UltimateModal(discord.ui.Modal, title='Preparar Ultimate'):
    gnose_input = discord.ui.TextInput(label='Gnose a Gastar (0-100)', style=discord.TextStyle.short)
    sp_input = discord.ui.TextInput(label='Perícia a Gastar (0-10)', style=discord.TextStyle.short)
    acao_input = discord.ui.TextInput(label='Descrição da Ação', style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Ultimate processada!", ephemeral=True)

class RaidPainelView(discord.ui.View):
    def __init__(self, turno_atual: int):
        super().__init__(timeout=None)
        self.turno_atual = turno_atual

    @discord.ui.button(label="Avançar Turno", style=discord.ButtonStyle.primary, custom_id="btn_avancar")
    async def btn_avancar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.turno_atual += 1
        await interaction.response.send_message(f"O Turno avançou para {self.turno_atual}.", ephemeral=False)

    @discord.ui.button(label="Descansar", style=discord.ButtonStyle.secondary, custom_id="btn_descansar")
    async def btn_descansar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Você adotou postura defensiva para o próximo turno.", ephemeral=True)

    @discord.ui.button(label="⚠️ Desferir Ultimate", style=discord.ButtonStyle.danger, custom_id="btn_ult")
    async def btn_ult(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UltimateModal())