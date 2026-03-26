"""
main.py — Guaxinim Bot
Entry point: slash commands, captura de `atk` via Tupperbox (on_message),
orquestração geral.
"""

from __future__ import annotations
import os
import re
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from config import GUILD_ID, ZONAS
from ficha import (
    FichaPersonagem, carregar_ficha_por_tupper, carregar_ficha_por_nome,
    salvar_ficha, deletar_ficha, criar_ficha_interativa, FichaParseError,
    carregar_ficha_por_dono,
)
from engine import CombatEngine
from brain import avaliar_acao
from ui_mvp import build_embed_ataque, embed_ficha
from debuff import (
    processar_tick_debuffs, aplicar_escudo, verificar_atordoamento,
    consumir_atordoamento,
)
from elementos import normalizar_elemento

load_dotenv()

# ─────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True   # necessário para capturar mensagens Tupperbox

bot = commands.Bot(command_prefix="!", intents=intents)
guild_obj = discord.Object(id=GUILD_ID)


@bot.event
async def on_ready():
    await bot.tree.sync(guild=guild_obj)
    print(f"[Guaxinim Bot] Online como {bot.user} | Comandos sincronizados.")


# ─────────────────────────────────────────
# ON_MESSAGE — CAPTURA ATK TUPPERBOX
# Qualquer mensagem de webhook com 'atk' no conteúdo
# ─────────────────────────────────────────

@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)

    # Só processa webhooks (Tupperbox envia como webhook)
    if not message.webhook_id:
        return

    content = message.content.strip()

    # Formato esperado: atk (ação) ou atk/def/combo etc.
    # Captura qualquer mensagem com 'atk' no início ou após espaço
    if not re.search(r'\batk\b', content, re.IGNORECASE):
        return

    # Nome do personagem = display_name do webhook
    tupper_name = message.author.display_name

    ficha_atacante = carregar_ficha_por_tupper(tupper_name)
    if ficha_atacante is None:
        await message.channel.send(
            f"⚠️ Personagem **{tupper_name}** não encontrado. "
            f"Peça ao admin para registrar com `/ficha_registrar`.",
            delete_after=10,
        )
        return

    # Extrai a ação — tudo após 'atk'
    match = re.search(r'\batk\s*(.*)', content, re.IGNORECASE | re.DOTALL)
    acao = match.group(1).strip() if match and match.group(1) else "ataca"

    # Verifica atordoamento
    if verificar_atordoamento(ficha_atacante):
        consumir_atordoamento(ficha_atacante)
        await message.channel.send(
            f"💫 **{tupper_name}** está **Atordoado** e não pode agir neste turno!",
            reference=message,
        )
        return

    # Detecta alvo na ação (menciona @alguém ou nome)
    # Por ora, usa o primeiro personagem diferente do atacante como alvo padrão
    # TODO: parsing de alvo mais robusto com /raid_definir_alvo
    alvo_nome = _extrair_alvo_da_acao(acao, ficha_atacante.nome)
    ficha_alvo = carregar_ficha_por_nome(alvo_nome) if alvo_nome else None

    if ficha_alvo is None:
        await message.channel.send(
            f"⚠️ Alvo não identificado na ação de **{tupper_name}**. "
            f"Mencione o nome do alvo ou use `/atk_definir_alvo`.",
            reference=message,
        )
        return

    # ── Avalia ação com IA (VA) ───────────
    avaliacao = await avaliar_acao(
        nome_personagem=ficha_atacante.nome,
        acao=acao,
        elemento=ficha_atacante.elemento_main,
        zona=ficha_atacante.zona,
        alvo=ficha_alvo.nome,
    )

    if not avaliacao.get("valida", True):
        await message.channel.send(
            f"❌ **Ação inválida** — {avaliacao.get('motivo_invalido', 'Mestre não aprovou.')}",
            reference=message,
        )
        return

    # ── Calcula dano ──────────────────────
    resultado = CombatEngine.calcular_ataque(
        atacante=ficha_atacante,
        alvo=ficha_alvo,
        acao=acao,
    )

    # Aplica dano real
    dano_real = ficha_alvo.receber_dano(resultado.dano_final)
    resultado.dano_real = dano_real
    resultado.hp_restante_alvo = ficha_alvo.hp_atual

    # Salva estados atualizados
    salvar_ficha(ficha_atacante)
    salvar_ficha(ficha_alvo)

    # ── Envia embed ──────────────────────
    embed = build_embed_ataque(resultado, ficha_alvo)

    # Comentário da IA como description extra
    comentario_ia = avaliacao.get("comentario", "")
    if comentario_ia:
        embed.add_field(name="🎭 Mestre", value=f"*{comentario_ia}*", inline=False)

    await message.channel.send(embed=embed, reference=message)

    # Morte
    if not ficha_alvo.esta_vivo:
        await message.channel.send(
            f"💀 **{ficha_alvo.nome}** foi derrotado!",
            reference=message,
        )


def _extrair_alvo_da_acao(acao: str, nome_atacante: str) -> str | None:
    """
    Heurística para detectar alvo mencionado na ação.
    Procura por 'em <Nome>' ou '@<Nome>' no texto.
    """
    match = re.search(r'(?:em|contra|@)\s+(\w+)', acao, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


# ─────────────────────────────────────────
# SLASH COMMANDS — JOGADORES
# ─────────────────────────────────────────

@bot.tree.command(guild=guild_obj, name="ficha_ver", description="Exibe sua ficha ou a de um personagem.")
@app_commands.describe(nome="Nome do personagem (deixe vazio para o seu)")
async def ficha_ver(interaction: discord.Interaction, nome: str | None = None):
    if nome:
        ficha = carregar_ficha_por_nome(nome)
    else:
        fichas = carregar_ficha_por_dono(interaction.user.id)
        ficha = fichas[0] if fichas else None

    if ficha is None:
        await interaction.response.send_message(
            "❌ Ficha não encontrada.", ephemeral=True
        )
        return

    await interaction.response.send_message(embed=embed_ficha(ficha))


@bot.tree.command(guild=guild_obj, name="descansar", description="Recupera toda a Gnose do seu personagem.")
@app_commands.describe(personagem="Nome do personagem")
async def descansar(interaction: discord.Interaction, personagem: str):
    ficha = carregar_ficha_por_nome(personagem)
    if ficha is None:
        await interaction.response.send_message("❌ Personagem não encontrado.", ephemeral=True)
        return

    # Verifica dono
    if ficha.dono_id != interaction.user.id:
        await interaction.response.send_message(
            "❌ Este personagem não é seu.", ephemeral=True
        )
        return

    recuperado = CombatEngine.descansar_gnose(ficha)
    salvar_ficha(ficha)

    await interaction.response.send_message(
        f"✨ **{ficha.nome}** descansou e recuperou **{recuperado}** de Gnose.\n"
        f"Gnose atual: `{ficha.gnose_atual}/{ficha.gnose_max}`"
    )


@bot.tree.command(guild=guild_obj, name="status", description="Exibe HP, Gnose e debuffs do personagem.")
@app_commands.describe(personagem="Nome do personagem")
async def status(interaction: discord.Interaction, personagem: str):
    ficha = carregar_ficha_por_nome(personagem)
    if ficha is None:
        await interaction.response.send_message("❌ Personagem não encontrado.", ephemeral=True)
        return
    await interaction.response.send_message(embed=embed_ficha(ficha))


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
# SLASH COMMANDS — ADMIN / MESTRE
# ─────────────────────────────────────────

@bot.tree.command(guild=guild_obj, name="ficha_registrar", description="[Admin] Registra uma ficha de personagem.")
@app_commands.describe(
    nome="Nome do personagem",
    dono="Jogador dono do personagem",
    tupper_name="Nome exato do webhook Tupperbox",
    plano="Main ou Paranormal",
    elemento="Elemento principal",
    elemento_sec="Variante paranormal (opcional)",
    str_="STR", res="RES", agi="AGI", sen="SEN", vit="VIT", int_="INT",
    rebirths="Número de Rebirths",
    gnose_max="Gnose máxima (padrão 9)",
    zona="Zona de poder (1-4)",
)
@app_commands.checks.has_permissions(manage_guild=True)
async def ficha_registrar(
    interaction: discord.Interaction,
    nome: str,
    dono: discord.Member,
    tupper_name: str,
    plano: str,
    elemento: str,
    str_: int, res: int, agi: int, sen: int, vit: int, int_: int,
    rebirths: int = 0,
    gnose_max: int = 9,
    zona: int = 1,
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
        await interaction.response.send_message(
            f"✅ Ficha de **{nome}** registrada com sucesso!",
            embed=embed_ficha(ficha),
        )
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

@bot.tree.command(guild=guild_obj, name="ficha_rebirth", description="[Admin] Adiciona rebirths e recalcula o HP do personagem.")
@app_commands.describe(
    personagem="Nome do personagem", 
    quantidade="Quantidade de rebirths para adicionar (Ex: 1)"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def ficha_rebirth(interaction: discord.Interaction, personagem: str, quantidade: int):
    # 1. Busca a ficha no banco de dados
    ficha = carregar_ficha_por_nome(personagem)
    if ficha is None:
        await interaction.response.send_message("❌ Personagem não encontrado.", ephemeral=True)
        return

    # 2. Aplica a progressão
    ficha.rebirths += quantidade
    
    # 3. Força o recálculo matemático da Vitalidade + Rebirths
    ficha.recalcular_hp_max()
    
    # 4. Salva a alteração no disco
    salvar_ficha(ficha)

    await interaction.response.send_message(
        f"🔄 **{ficha.nome}** transcendeu e recebeu **+{quantidade}** Rebirth(s)!\n"
        f"Rebirths totais: `{ficha.rebirths}`\n"
        f"Novo HP Máximo: `{ficha.hp_max}`"
    )


@bot.tree.command(guild=guild_obj, name="raid_zona", description="[Admin] Define a zona atual do raid.")
@app_commands.describe(zona="Zona (1-4)")
@app_commands.checks.has_permissions(manage_guild=True)
async def raid_zona(interaction: discord.Interaction, zona: int):
    if zona not in ZONAS:
        await interaction.response.send_message("❌ Zona inválida (1-4).", ephemeral=True)
        return
    
    import json
    import os
    arquivo = "raid_estado.json"
    estado = {}
    
    # Lê os dados existentes se o arquivo existir
    if os.path.exists(arquivo) and os.path.getsize(arquivo) > 0:
        with open(arquivo, "r", encoding="utf-8") as f:
            estado = json.load(f)
            
    # Atualiza e salva sobrescrevendo/criando o arquivo (modo "w")
    estado["zona"] = zona
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2)
        
    await interaction.response.send_message(
        f"🌀 Zona do raid definida como **Zona {zona} — {ZONAS[zona]['nome']}**."
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
    await interaction.response.send_message(
        f"{msg}\nHP: `{ficha.hp_atual}/{ficha.hp_max}`"
    )


@bot.tree.command(guild=guild_obj, name="boss_template", description="[Admin] Define personalidade do boss (texto livre).")
@app_commands.describe(boss="Nome do boss", texto="Personalidade/contexto para a IA")
@app_commands.checks.has_permissions(manage_guild=True)
async def boss_template(interaction: discord.Interaction, boss: str, texto: str):
    import json
    path = "boss_personalidades.json"
    data = {}
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
    data[boss.lower()] = texto
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    await interaction.response.send_message(
        f"✅ Personalidade do boss **{boss}** configurada.", ephemeral=True
    )


@bot.tree.command(guild=guild_obj, name="forca_aprovacao", description="[Admin] Aprova ou bloqueia ação pendente.")
@app_commands.describe(aprovado="True = aprova, False = bloqueia")
@app_commands.checks.has_permissions(manage_guild=True)
async def forca_aprovacao(interaction: discord.Interaction, aprovado: bool):
    # Placeholder — integração com fila de ações pendentes (Fase 3)
    status = "✅ Aprovada" if aprovado else "❌ Bloqueada"
    await interaction.response.send_message(f"Ação {status} pelo Mestre.", ephemeral=True)


# ─────────────────────────────────────────
# ERRO GLOBAL DE PERMISSÃO
# ─────────────────────────────────────────

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando.", ephemeral=True
        )
    else:
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
        print("❌ BOT_TOKEN não definido no .env")
    else:
        bot.run(token)
