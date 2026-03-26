"""
debuff.py — Guaxinim Bot
Gerenciamento de status persistentes: debuffs, escudos, efeitos por turno.
"""

from __future__ import annotations
from config import DEBUFFS
from ficha import FichaPersonagem, salvar_ficha


# ─────────────────────────────────────────
# EFEITOS POR TURNO (tick)
# ─────────────────────────────────────────

def processar_tick_debuffs(personagem: FichaPersonagem) -> list[str]:
    """
    Processa os debuffs no início/fim de turno.
    Aplica dano de DoT (Queimadura, Sangramento) e remove os expirados.
    Retorna lista de mensagens para o embed de resultado.
    """
    mensagens = []

    for debuff in list(personagem.debuffs):
        nome = debuff["nome"]

        # Dano por turno (DoT)
        if nome == "Queimadura":
            dano_dot = max(1, personagem.hp_max // 20)   # 5% HP máx por turno
            aplicado = personagem.receber_dano(dano_dot)
            mensagens.append(f"🔥 **Queimadura** causou **{aplicado}** de dano.")

        elif nome == "Sangramento":
            dano_dot = max(1, int(personagem.hp_max * 0.07))  # 7% HP máx
            aplicado = personagem.receber_dano(dano_dot)
            mensagens.append(f"🩸 **Sangramento** causou **{aplicado}** de dano.")

    # Avança duração e remove expirados
    expirados = personagem.tick_debuffs()
    for nome_exp in expirados:
        emoji = DEBUFFS.get(nome_exp, {}).get("emoji", "✅")
        mensagens.append(f"{emoji} **{nome_exp}** expirou.")

    salvar_ficha(personagem)
    return mensagens


# ─────────────────────────────────────────
# ESCUDO / BARREIRA
# ─────────────────────────────────────────

def aplicar_escudo(personagem: FichaPersonagem, valor: int) -> int:
    """
    Adiciona um escudo temporário ao personagem.
    O escudo absorve dano antes do HP.
    Armazenado como debuff especial com duração de 1 turno.
    Retorna valor do escudo aplicado.
    """
    # Escudo é modelado como debuff especial "Escudo" com campo extra "valor"
    personagem.adicionar_debuff("Escudo", duracao=1, valor=valor)
    salvar_ficha(personagem)
    return valor


def absorver_dano_escudo(personagem: FichaPersonagem, dano: int) -> tuple[int, int]:
    """
    Tenta absorver dano com escudo ativo.
    Retorna (dano_restante, dano_absorvido).
    """
    for debuff in personagem.debuffs:
        if debuff["nome"] == "Escudo":
            valor_escudo = debuff.get("valor", 0)
            absorvido = min(valor_escudo, dano)
            debuff["valor"] -= absorvido
            if debuff["valor"] <= 0:
                personagem.debuffs.remove(debuff)
            return dano - absorvido, absorvido
    return dano, 0


# ─────────────────────────────────────────
# ATORDOAMENTO / SKIP DE TURNO
# ─────────────────────────────────────────

def verificar_atordoamento(personagem: FichaPersonagem) -> bool:
    """Retorna True se o personagem está atordoado (não pode agir)."""
    return personagem.tem_debuff("Atordoado")


def consumir_atordoamento(personagem: FichaPersonagem):
    """Remove o debuff de Atordoado após o turno ser pulado."""
    personagem.debuffs = [d for d in personagem.debuffs if d["nome"] != "Atordoado"]
    salvar_ficha(personagem)


# ─────────────────────────────────────────
# FORMATAÇÃO PARA EMBED
# ─────────────────────────────────────────

def formatar_debuffs_embed(personagem: FichaPersonagem) -> str:
    """
    Retorna string formatada com todos os debuffs ativos para uso em embed.
    Ex: "🩸 Sangramento (2t)  ❄️ Congelado (1t)"
    """
    if not personagem.debuffs:
        return "✅ Nenhum"

    partes = []
    for d in personagem.debuffs:
        nome = d["nome"]
        dur  = d.get("duracao", "?")
        emoji = DEBUFFS.get(nome, {}).get("emoji", "⚠️")
        if nome == "Escudo":
            partes.append(f"🛡️ Escudo ({d.get('valor', 0)} HP)")
        else:
            partes.append(f"{emoji} {nome} ({dur}t)")

    return "  ".join(partes)


def formatar_debuffs_lista(personagem: FichaPersonagem) -> list[str]:
    """Retorna lista de strings para cada debuff (para campos separados em embed)."""
    resultado = []
    for d in personagem.debuffs:
        nome  = d["nome"]
        dur   = d.get("duracao", "?")
        emoji = DEBUFFS.get(nome, {}).get("emoji", "⚠️")
        desc  = DEBUFFS.get(nome, {}).get("descricao", "")
        if nome == "Escudo":
            resultado.append(f"🛡️ **Escudo** — absorve {d.get('valor', 0)} HP")
        else:
            resultado.append(f"{emoji} **{nome}** ({dur}t) — {desc}")
    return resultado
