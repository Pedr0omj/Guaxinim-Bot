"""
debuff.py — Guaxinim Bot
Gerenciamento de status persistentes: debuffs, escudos, efeitos de turno.

CORRIGIDO: absorber_dano_escudo agora chama salvar_ficha ao final.
"""

from __future__ import annotations
import logging
from config import DEBUFFS
from ficha import FichaPersonagem, salvar_ficha

# ADICIONADO: Logging para rastrear aplicação de debuffs e DoT em combates
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# EFEITOS POR TURNO (tick)
# ─────────────────────────────────────────

def processar_tick_debuffs(personagem: FichaPersonagem, persistir: bool = True) -> list[str]:
    """
    Processa debuffs no início/fim de turno.
    Aplica DoT (Queimadura, Sangramento) e remove os expirados.
    """
    mensagens = []

    for debuff in list(personagem.debuffs):
        nome = debuff["nome"]

        if nome == "Queimadura":
            dano_dot = max(1, personagem.hp_max // 20)
            aplicado = personagem.receber_dano(dano_dot)
            # ADICIONADO: Logging de DoT para rastreamento de combate
            logger.debug(f"{personagem.nome} - Queimadura: {aplicado} dano aplicado")
            mensagens.append(f"🔥 **Queimadura** causou **{aplicado}** de dano.")

        elif nome == "Sangramento":
            dano_dot = max(1, int(personagem.hp_max * 0.07))
            aplicado = personagem.receber_dano(dano_dot)
            # ADICIONADO: Logging de DoT para rastreamento de combate
            logger.debug(f"{personagem.nome} - Sangramento: {aplicado} dano aplicado")
            mensagens.append(f"🩸 **Sangramento** causou **{aplicado}** de dano.")

    expirados = personagem.tick_debuffs()
    for nome_exp in expirados:
        emoji = DEBUFFS.get(nome_exp, {}).get("emoji", "✅")
        # ADICIONADO: Log quando debuff expira
        logger.debug(f"{personagem.nome} - {nome_exp} expirou")
        mensagens.append(f"{emoji} **{nome_exp}** expirou.")

    # ADICIONADO: Eu permiti desligar persistência síncrona aqui para cenários assíncronos
    # (ex.: virada de turno em lote), evitando I/O bloqueante no loop principal.
    if persistir:
        salvar_ficha(personagem)
    return mensagens


# ─────────────────────────────────────────
# ESCUDO / BARREIRA
# ─────────────────────────────────────────

def aplicar_escudo(personagem: FichaPersonagem, valor: int) -> int:
    """
    Adiciona escudo temporário. Duração = 1 turno.
    Retorna valor do escudo aplicado.
    """
    personagem.adicionar_debuff("Escudo", duracao=1, valor=valor)
    # ADICIONADO: Logging de escudos aplicados
    logger.debug(f"{personagem.nome} - Escudo de {valor} HP aplicado")
    salvar_ficha(personagem)
    return valor


def absorver_dano_escudo(personagem: FichaPersonagem, dano: int) -> tuple[int, int]:
    """
    Tenta absorver dano com escudo ativo.
    Retorna (dano_restante, dano_absorvido).

    CORREÇÃO: salva a ficha após modificar o escudo.
    """
    for debuff in personagem.debuffs:
        if debuff["nome"] == "Escudo":
            valor_escudo = debuff.get("valor", 0)
            absorvido = min(valor_escudo, dano)
            debuff["valor"] -= absorvido
            # ADICIONADO: Logging quando escudo absorve dano
            logger.debug(f"{personagem.nome} - Escudo absorveu {absorvido} de dano ({valor_escudo - absorvido} restante)")
            if debuff["valor"] <= 0:
                personagem.debuffs.remove(debuff)
                logger.debug(f"{personagem.nome} - Escudo quebrou")
            salvar_ficha(personagem)   # CORREÇÃO: persistir após absorção
            return dano - absorvido, absorvido
    return dano, 0


# ─────────────────────────────────────────
# ATORDOAMENTO / SKIP DE TURNO
# ─────────────────────────────────────────

def verificar_atordoamento(personagem: FichaPersonagem) -> bool:
    return personagem.tem_debuff("Atordoado")


def consumir_atordoamento(personagem: FichaPersonagem):
    personagem.debuffs = [d for d in personagem.debuffs if d["nome"] != "Atordoado"]
    salvar_ficha(personagem)


# ─────────────────────────────────────────
# FORMATAÇÃO PARA EMBED
# ─────────────────────────────────────────

def formatar_debuffs_embed(personagem: FichaPersonagem) -> str:
    """Return compact string of active debuffs for embeds."""
    if not personagem.debuffs:
        return "✅ None"

    partes = []
    for d in personagem.debuffs:
        nome  = d["nome"]
        # CORRIGIDO: Eu estava procurando pela chave 'duration' em inglês, mas em ficha.py
        # os debuffs são salvos com a chave 'duracao' em português. Ajustei para buscar
        # a chave correta para que a duração seja exibida corretamente no embed.
        dur   = d.get("duracao", "?")
        emoji = DEBUFFS.get(nome, {}).get("emoji", "⚠️")
        if nome == "Escudo":
            partes.append(f"🛡️ Shield ({d.get('valor', 0)} HP)")
        # ADICIONADO: DefesaAtiva é um buff de defesa (não é debuff negativo)
        # Mostra como escudo ativo ao invés de efeito negativo
        elif nome == "DefesaAtiva":
            partes.append(f"🛡️ Defesa Ativa ({dur}t)")
        else:
            partes.append(f"{emoji} {nome} ({dur}t)")

    return "  ".join(partes)


def formatar_debuffs_lista(personagem: FichaPersonagem) -> list[str]:
    """List of strings per debuff (for separate fields in embed)."""
    resultado = []
    for d in personagem.debuffs:
        nome  = d["nome"]
        # CORRIGIDO: Mesma correção anterior - usando 'duracao' ao invés de 'duration'
        # para manter consistência com como os debuffs são armazenados em ficha.py
        dur   = d.get("duracao", "?")
        emoji = DEBUFFS.get(nome, {}).get("emoji", "⚠️")
        desc  = DEBUFFS.get(nome, {}).get("description", "")
        if nome == "Escudo":
            resultado.append(f"🛡️ **Shield** — absorbs {d.get('valor', 0)} HP")
        # ADICIONADO: DefesaAtiva mostra como buff de defesa (positivo)
        elif nome == "DefesaAtiva":
            resultado.append(f"🛡️ **Defesa Ativa** ({dur}t) — {desc}")
        else:
            resultado.append(f"{emoji} **{nome}** ({dur}t) — {desc}")
    return resultado
