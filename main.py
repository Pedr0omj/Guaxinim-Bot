"""
main.py — Guaxinim Bot
Entry point: slash commands, captura de ações via Tupperbox (on_message).
"""

from __future__ import annotations
import os
import re
import json
import time
import logging

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from cachetools import TTLCache

from config import GUILD_ID, ZONAS
from ficha import (
    FichaPersonagem, carregar_ficha_por_tupper, carregar_ficha_por_nome,
    salvar_ficha, deletar_ficha, criar_ficha_interativa, FichaParseError,
    carregar_ficha_por_dono,
)
from engine import CombatEngine
from brain import avaliar_acao
from ui_mvp import build_mensagem_ataque, build_mensagem_ficha, AtaqueView, RaidPainelView
from debuff import (
    processar_tick_debuffs, aplicar_escudo,
    verificar_atordoamento, consumir_atordoamento,
)
from elementos import normalizar_elemento

load_dotenv()

log = logging.getLogger("guaxinim")
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(levelname)s: %(message)s")

# ─────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
guild_obj = discord.Object(id=GUILD_ID)

# ─────────────────────────────────────────
# RATE LIMITING — anti-spam por personagem/canal
# ─────────────────────────────────────────

_cooldowns = TTLCache(maxsize=10000, ttl=3.0)
COOLDOWN_SEG = 3.0

def _check_cooldown(tupper_name: str, channel_id: int) -> bool:
    chave = f"{tupper_name.lower()}:{channel_id}"
    agora = time.monotonic()
    
    ultimo_uso = _cooldowns.get(chave, 0.0)
    
    if agora - ultimo_uso < COOLDOWN_SEG:
        return False
        
    _cooldowns[chave] = agora
    return True

# ─────────────────────────────────────────
# DETECÇÃO DE TEXTO DA AÇÃO
# ─────────────────────────────────────────

_RE_ACAO = re.compile(r'\*+(.+?)\*+', re.DOTALL)

def extrair_texto_acao(content: str) -> str | None:
    content_limpo = re.sub(r'^>.*$', '', content, flags=re.MULTILINE)
    m = _RE_ACAO.search(content_limpo)
    return m.group(1).strip() if m else None

# ─────────────────────────────────────────
# ON_READY
# ─────────────────────────────────────────

@bot.event
async def on_ready():
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync(guild=None)
    
    await bot.tree.sync(guild=guild_obj)
    
    log.info("Online como %s | Comandos sincronizados e limpos.", bot.user)

# ─────────────────────────────────────────
# ON_MESSAGE — CAPTURA AÇÕES TUPPERBOX
# ─────────────────────────────────────────

@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)

    if message.author == bot.user:
        return

    if not message.webhook_id:
        return

    content = message.content.strip()
    if not content:
        return

    acao = extrair_texto_acao(content)
    if not acao:
        return

    tupper_name = message.author.display_name

    if not _check_cooldown(tupper_name, message.channel.id):
        return

    ficha_atacante = carregar_ficha_por_tupper(tupper_name)
    if ficha_atacante is None:
        await message.channel.send(
            f"⚠️ Personagem **{tupper_name}** não encontrado. "
            f"Peça ao admin para registrar com `/ficha_registrar`.",
            delete_after=10,
        )
        return

    avaliacao = await avaliar_acao(
        nome_personagem=ficha_atacante.nome,
        acao=acao,
        elemento=ficha_atacante.elemento_main,
        zona=ficha_atacante.zona,
    )

    if not avaliacao.get("valida", True):
        await message.channel.send(
            f"❌ **Ação inválida** — {avaliacao.get('motivo_invalido', 'Mestre não aprovou.')}",
            reference=message,
        )
        return

    tipo = avaliacao.get("tipo", "ataque")
    
    if tipo == "defesa":
        await _processar_defesa(message, ficha_atacante, acao, avaliacao)
    else:
        alvo_nome = avaliacao.get("alvo")
        await _processar_ataque(message, ficha_atacante, acao, avaliacao, alvo_nome)

# ─────────────────────────────────────────
# HANDLER DE ATAQUE
# ─────────────────────────────────────────

async def _processar_ataque(
    message: discord.Message,
    ficha_atacante: FichaPersonagem,
    acao: str,
    avaliacao: dict,
    alvo_nome: str | None,
):
    if verificar_atordoamento(ficha_atacante):
        consumir_atordoamento(ficha_atacante)
        await message.channel.send(
            f"💫 **{ficha_atacante.nome}** está **Atordoado** e perde o turno!",
            reference=message,
        )
        return

    ficha_alvo = carregar_ficha_por_nome(alvo_nome) if alvo_nome else None

    if ficha_alvo is None:
        await message.channel.send(
            f"⚠️ O alvo `{alvo_nome}` detectado na ação não possui uma ficha registrada.\n"
            f"Dica para a IA ler melhor: `**Ataca em NomeDoAlvo**`",
            reference=message,
        )
        return

    # =======================================================
    # SISTEMA DE PERÍCIA (SP)
    # =======================================================
    categoria_acao = avaliacao.get("categoria_acao", "basico")
    
    if categoria_acao == "pericia":
        if ficha_atacante.sp_atual < 3:
            await message.channel.send(
                f"❌ **Falha de Requisito:** SP insuficiente (Atual: `{ficha_atacante.sp_atual}` | Mínimo: `3`).\n"
                f"**{ficha_atacante.nome}** tentou usar uma perícia exausto e perdeu o turno!",
                reference=message
            )
            return
        ficha_atacante.sp_atual -= 3
    else:
        ficha_atacante.sp_atual = min(ficha_atacante.sp_max, ficha_atacante.sp_atual + 1)
    # =======================================================

    va_ia = avaliacao.get("va", 5)
    gnose_antes = ficha_atacante.gnose_atual

    resultado = CombatEngine.calcular_ataque(
        atacante=ficha_atacante,
        alvo=ficha_alvo,
        acao=acao,
        va_override=va_ia,
    )

    if gnose_antes > 0 and ficha_atacante.gnose_atual <= 0:
        resultado.gnose_esgotada_antes = True

    dano_real = ficha_alvo.receber_dano(resultado.dano_final)
    resultado.dano_real = dano_real
    resultado.hp_restante_alvo = ficha_alvo.hp_atual

    salvar_ficha(ficha_atacante)
    salvar_ficha(ficha_alvo)

    comentario_ia = avaliacao.get("comentario", "")
    texto, view = build_mensagem_ataque(resultado, ficha_alvo, ficha_atacante, comentario_ia)

    await message.channel.send(content=texto, view=view, reference=message)

    if not ficha_alvo.esta_vivo:
        await message.channel.send(
            f"💀 **{ficha_alvo.nome}** foi derrotado!",
            reference=message,
        )

# ─────────────────────────────────────────
# HANDLER DE DEFESA
# ─────────────────────────────────────────

async def _processar_defesa(
    message: discord.Message,
    ficha_defensor: FichaPersonagem,
    acao: str,
    avaliacao: dict,
):
    resultado_def = CombatEngine.calcular_defesa(ficha_defensor)
    comentario_ia = avaliacao.get("comentario", "")

    if resultado_def["sucesso"]:
        texto = (
            f"🛡️ **{ficha_defensor.nome}** se defende!\n"
            f"> *{acao}*\n\n"
            f"✅ Esquiva/Bloqueio bem-sucedido! "
            f"Chance: `{resultado_def['chance']:.0f}%` · AGI `{resultado_def['agi_usado']}`\n"
            f"O próximo dano recebido será reduzido em **50%**.\n"
            f"🎭 *\"{comentario_ia}\"*" if comentario_ia else ""
        )
    else:
        texto = (
            f"💢 **{ficha_defensor.nome}** tentou se defender...\n"
            f"> *{acao}*\n\n"
            f"❌ Falhou. Chance era `{resultado_def['chance']:.0f}%` · AGI `{resultado_def['agi_usado']}`\n"
            f"🎭 *\"{comentario_ia}\"*" if comentario_ia else ""
        )

    await message.channel.send(content=texto, reference=message)

# ─────────────────────────────────────────
# SLASH COMMANDS — JOGADORES
# ─────────────────────────────────────────

@bot.tree.command(guild=guild_obj, name="ficha_ver", description="Exibe a ficha interativa de um personagem.")
@app_commands.describe(nome="Nome do personagem (deixe vazio para o seu)")
async def ficha_ver(interaction: discord.Interaction, nome: str | None = None):
    if nome:
        ficha = carregar_ficha_por_nome(nome)
    else:
        fichas = carregar_ficha_por_dono(interaction.user.id)
        ficha = fichas[0] if fichas else None

    if ficha is None:
        await interaction.response.send_message("❌ Ficha não encontrada.", ephemeral=True)
        return

    dono_obj = interaction.guild.get_member(ficha.dono_id) if interaction.guild else None
    
    embed, view = build_mensagem_ficha(ficha, dono_obj)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(guild=guild_obj, name="status", description="Acesso rápido aos status de combate.")
@app_commands.describe(personagem="Nome do personagem")
async def status(interaction: discord.Interaction, personagem: str):
    ficha = carregar_ficha_por_nome(personagem)
    if ficha is None:
        await interaction.response.send_message("❌ Personagem não encontrado.", ephemeral=True)
        return
        
    dono_obj = interaction.guild.get_member(ficha.dono_id) if interaction.guild else None
    embed, view = build_mensagem_ficha(ficha, dono_obj)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(guild=guild_obj, name="descansar", description="Recupera toda a Gnose do seu personagem.")
@app_commands.describe(personagem="Nome do personagem")
async def descansar(interaction: discord.Interaction, personagem: str):
    ficha = carregar_ficha_por_nome(personagem)
    if ficha is None:
        await interaction.response.send_message("❌ Personagem não encontrado.", ephemeral=True)
        return

    if ficha.dono_id != interaction.user.id:
        await interaction.response.send_message("❌ Este personagem não é seu.", ephemeral=True)
        return

    recuperado = CombatEngine.descansar_gnose(ficha)
    salvar_ficha(ficha)

    await interaction.response.send_message(
        f"✨ **{ficha.nome}** descansou e recuperou **{recuperado}** de Gnose.\n"
        f"Gnose atual: `{ficha.gnose_atual}/{ficha.gnose_max}`"
    )

@bot.tree.command(guild=guild_obj, name="guaxinim_chat", description="Conversa diretamente com o Mestre IA.")
@app_commands.describe(mensagem="Sua mensagem para o Mestre")
async def guaxinim_chat(interaction: discord.Interaction, mensagem: str):
    from brain import gerar_resposta_boss
    resposta = await gerar_resposta_boss(
        personalidade="Sábio e misterioso narrador de RPG",
        situacao=mensagem,
        hp_percentual=1.0,
    )
    await interaction.response.send_message(f"🎭 *{resposta}*")

# ─────────────────────────────────────────
# SLASH COMMANDS — ADMIN
# ─────────────────────────────────────────

@bot.tree.command(guild=guild_obj, name="painel_raid", description="[Admin] Inicia o painel interativo de turnos e ultimates.")
@app_commands.checks.has_permissions(manage_guild=True)
async def painel_raid(interaction: discord.Interaction):
    view = RaidPainelView(turno_atual=1)
    
    embed = discord.Embed(
        title="⚔️ Painel de Controle da Raid",
        description="Utilize os botões abaixo para gerenciar a batalha.",
        color=0xC0392B
    )
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(guild=guild_obj, name="ficha_registrar", description="[Admin] Registra uma ficha de personagem.")
@app_commands.describe(
    nome="Nome do personagem", dono="Jogador dono",
    tupper_name="Nome exato do webhook Tupperbox",
    plano="Main ou Paranormal", elemento="Elemento principal",
    elemento_sec="Variante paranormal (opcional)",
    str_="STR", res="RES", agi="AGI", sen="SEN", vit="VIT", int_="INT",
    rebirths="Rebirths", gnose_max="Gnose máx (Padrão 100)", zona="Zona (1-4)",
)
@app_commands.rename(str_="str", int_="int")
@app_commands.choices(
    plano=[
        app_commands.Choice(name="Main", value="Main"),
        app_commands.Choice(name="Paranormal", value="Paranormal")
    ],
    elemento=[
        app_commands.Choice(name="🔥 Fogo", value="Fogo"),
        app_commands.Choice(name="❄️ Gelo", value="Gelo"),
        app_commands.Choice(name="⚡ Raio", value="Raio"),
        app_commands.Choice(name="🌪️ Vento", value="Vento"),
        app_commands.Choice(name="🔮 Quantum", value="Quantum"),
        app_commands.Choice(name="🌀 Imaginário", value="Imaginario"),
        app_commands.Choice(name="⚔️ Físico", value="Fisico")
    ],
    elemento_sec=[
        app_commands.Choice(name="💀 Morte", value="Morte"),
        app_commands.Choice(name="🩸 Sangue", value="Sangue"),
        app_commands.Choice(name="👁️ Conhecimento", value="Conhecimento"),
        app_commands.Choice(name="⚡ Energia", value="Energia"),
        app_commands.Choice(name="😨 Medo", value="Medo"),
        app_commands.Choice(name="🌑 Corrupção", value="Corrupcao"),
        app_commands.Choice(name="✨ Astral", value="Astral"),
        app_commands.Choice(name="🌟 Sagrado", value="Sagrado"),
        app_commands.Choice(name="🌌 Abismo", value="Abismo"),
        app_commands.Choice(name="🌪️ Tempestade", value="Tempestade"),
        app_commands.Choice(name="⛓️ Maldição", value="Maldicao")
    ],
    zona=[
        app_commands.Choice(name="Zona 1 — Humano/Físico", value=1),
        app_commands.Choice(name="Zona 2 — Poderes Básicos", value=2),
        app_commands.Choice(name="Zona 3 — Habilidades Avançadas", value=3),
        app_commands.Choice(name="Zona 4 — Conceitual/Max", value=4)
    ]
)
@app_commands.checks.has_permissions(manage_guild=True)
async def ficha_registrar(
    interaction: discord.Interaction,
    nome: str, dono: discord.Member, tupper_name: str,
    plano: str, elemento: str,
    str_: int, res: int, agi: int, sen: int, vit: int, int_: int,
    rebirths: int = 0, gnose_max: int = 100, zona: int = 1,
    elemento_sec: str | None = None,
):
    try:
        ficha = criar_ficha_interativa(
            nome=nome, dono_id=dono.id, tupper_name=tupper_name,
            plano=plano, elemento=elemento, elemento_secundario=elemento_sec,
            str_=str_, res=res, agi=agi, sen=sen, vit=vit, int_=int_,
            rebirths=rebirths, gnose_max=gnose_max, zona=zona,
        )
        salvar_ficha(ficha)
        
        embed, view = build_mensagem_ficha(ficha, dono)
        await interaction.response.send_message(f"✅ Ficha de **{nome}** registrada!", embed=embed, view=view)
    except FichaParseError as e:
        await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)


@bot.tree.command(guild=guild_obj, name="ficha_deletar", description="[Admin] Remove uma ficha.")
@app_commands.describe(nome="Nome do personagem")
@app_commands.checks.has_permissions(manage_guild=True)
async def ficha_deletar(interaction: discord.Interaction, nome: str):
    if deletar_ficha(nome):
        await interaction.response.send_message(f"🗑️ Ficha **{nome}** removida.")
    else:
        await interaction.response.send_message(f"❌ Ficha **{nome}** não encontrada.", ephemeral=True)

@bot.tree.command(guild=guild_obj, name="ficha_rebirth", description="[Admin] Adiciona rebirths e recalcula HP.")
@app_commands.describe(personagem="Nome do personagem", quantidade="Quantidade de rebirths")
@app_commands.checks.has_permissions(manage_guild=True)
async def ficha_rebirth(interaction: discord.Interaction, personagem: str, quantidade: int):
    ficha = carregar_ficha_por_nome(personagem)
    if ficha is None:
        await interaction.response.send_message("❌ Personagem não encontrado.", ephemeral=True)
        return
    ficha.rebirths += quantidade
    ficha.recalcular_hp_max()
    salvar_ficha(ficha)
    await interaction.response.send_message(
        f"🔄 **{ficha.nome}** recebeu **+{quantidade}** Rebirth(s)!\n"
        f"Total: `{ficha.rebirths}` · HP Máx: `{ficha.hp_max}`"
    )

@bot.tree.command(guild=guild_obj, name="raid_zona", description="[Admin] Define a zona do raid.")
@app_commands.describe(zona="Zona (1-4)")
@app_commands.checks.has_permissions(manage_guild=True)
async def raid_zona(interaction: discord.Interaction, zona: int):
    if zona not in ZONAS:
        await interaction.response.send_message("❌ Zona inválida (1-4).", ephemeral=True)
        return
    arquivo = "raid_estado.json"
    estado = {}
    if os.path.exists(arquivo) and os.path.getsize(arquivo) > 0:
        with open(arquivo, "r", encoding="utf-8") as f:
            estado = json.load(f)
    estado["zona"] = zona
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2)
    await interaction.response.send_message(
        f"🌀 Zona definida: **Zona {zona} — {ZONAS[zona]['nome']}**."
    )

@bot.tree.command(guild=guild_obj, name="boss_kill_heal", description="[Admin] Dano ou cura no boss.")
@app_commands.describe(boss="Nome do boss", valor="Positivo = dano, negativo = cura")
@app_commands.checks.has_permissions(manage_guild=True)
async def boss_kill_heal(interaction: discord.Interaction, boss: str, valor: int):
    ficha = carregar_ficha_por_nome(boss)
    if ficha is None:
        await interaction.response.send_message("❌ Boss não encontrado.", ephemeral=True)
        return
    if valor > 0:
        aplicado = ficha.receber_dano(valor)
        msg = f"💥 **{boss}** recebeu **{aplicado}** de dano."
    else:
        curado = ficha.curar(abs(valor))
        msg = f"💚 **{boss}** foi curado em **{curado}** HP."
    salvar_ficha(ficha)
    await interaction.response.send_message(f"{msg}\nHP: `{ficha.hp_atual}/{ficha.hp_max}`")

@bot.tree.command(guild=guild_obj, name="boss_template", description="[Admin] Define personalidade do boss.")
@app_commands.describe(boss="Nome do boss", texto="Personalidade para a IA")
@app_commands.checks.has_permissions(manage_guild=True)
async def boss_template(interaction: discord.Interaction, boss: str, texto: str):
    path = "boss_personalidades.json"
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data[boss.lower()] = texto
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    await interaction.response.send_message(
        f"✅ Personalidade de **{boss}** configurada.", ephemeral=True
    )

# ─────────────────────────────────────────
# ERRO GLOBAL
# ─────────────────────────────────────────

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Você não tem permissão para este comando.", ephemeral=True
        )
    else:
        log.exception("Erro em app command: %s", error)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"❌ Erro inesperado: {error}", ephemeral=True
            )
        raise error

# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        log.error("BOT_TOKEN não definido no .env")
    else:
        bot.run(token)