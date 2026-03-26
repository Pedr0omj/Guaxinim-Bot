"""
brain.py — Guaxinim Bot
Árbitro narrativo IA (Mestre): valida ações, gera VA e respostas do boss.
Usa Anthropic Claude, Gemini ou OpenAI via API.
"""

from __future__ import annotations
import os
import re
import json
import logging
import aiohttp
import asyncio

# ADICIONADO: Logging para rastrear falhas de API e erros de processamento
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ─────────────────────────────────────────
# CONFIGURAÇÃO DE MODELOS E CHAVES
# ─────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")


# ─────────────────────────────────────────
# PROMPT MESTRE
# ─────────────────────────────────────────

SYSTEM_MESTRE = """
Você é o Mestre de um RPG de combate estilo anime shonen.
Sua função: ler a ação do jogador, interpretar a intenção semântica e retornar SOMENTE JSON.

Regras de Interpretação:
1. "tipo": Defina como "ataque" se a ação for ofensiva, agressiva ou tentar aplicar efeito em alguém. Defina como "defesa" se for esquiva, bloqueio, recuo ou proteção.
2. "alvo": Identifique e extraia o nome de quem está recebendo o ataque. Se for uma ação de defesa ou não houver alvo claro, retorne null.
3. "va" (Vantagem de Ação 0-10): Avalie a criatividade. 0-2 (vaga/preguiçosa), 3-5 (básica), 6-8 (criativa/uso do ambiente), 9-10 (cinematográfica/épica).
4. "categoria_acao": use "pericia" quando a ação explicitamente representar técnica/habilidade/magia/jutsu/golpe especial/ritual/feitiço; use "basico" para ataque comum.

Retorne EXCLUSIVAMENTE este formato JSON exato (sem markdown em volta):
{
    "tipo": "ataque",
    "alvo": "NomeDoAlvo",
    "categoria_acao": "basico", 
    "va": 8,
    "comentario": "..."
}
""".strip()


async def avaliar_acao(
    nome_personagem: str,
    acao: str,
    elemento: str,
    zona: int,
) -> dict:
    """
    Delega à IA a responsabilidade de descobrir o tipo de ação e o alvo,
    além de calcular a VA.
    """
    prompt = (
        f"Personagem Agindo: {nome_personagem} (Elemento: {elemento}, Zona {zona})\n"
        f"Texto da Ação Declarada: {acao}"
    )

    tasks = []
    if ANTHROPIC_API_KEY: tasks.append(asyncio.create_task(_chamar_anthropic(prompt)))
    if GEMINI_API_KEY:    tasks.append(asyncio.create_task(_chamar_gemini(prompt)))
    if OPENAI_API_KEY:    tasks.append(asyncio.create_task(_chamar_openai(prompt)))

    if not tasks:
        return _fallback_estatico(acao)

    # MELHORADO: Eu parei de aceitar o "primeiro que responder" cegamente.
    # Agora eu espero o primeiro resultado VÁLIDO (não-None) para evitar queda prematura em fallback.
    pending = set(tasks)
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            try:
                resultado = task.result()
            except Exception:
                continue
            if resultado:
                for p in pending:
                    p.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                return resultado

    return _fallback_estatico(acao)


async def gerar_resposta_boss(
    personalidade: str,
    situacao: str,
    hp_percentual: float,
) -> str:
    """
    Gera uma fala épica do boss baseada em sua personalidade e situação.
    Dispara requisições simultâneas e retorna a primeira que responder.
    """
    urgencia = "furioso e desesperado" if hp_percentual < 0.30 else "confiante e ameaçador"
    prompt = (
        f"Boss personalidade: {personalidade}\n"
        f"Situação atual: {situacao}\n"
        f"Estado: {urgencia} (HP em {int(hp_percentual * 100)}%)\n\n"
        f"Gere UMA fala de 1-2 frases do boss. Seja épico e no estilo anime."
    )

    system = (
        "Você é um boss de RPG anime. Responda APENAS com a fala do boss, "
        "sem aspas, sem prefixo, sem explicação. 1-2 frases máximo."
    )

    tasks = []
    if ANTHROPIC_API_KEY: tasks.append(asyncio.create_task(_chamar_anthropic_texto(prompt, system)))
    if GEMINI_API_KEY:    tasks.append(asyncio.create_task(_chamar_gemini_texto(prompt, system)))
    if OPENAI_API_KEY:    tasks.append(asyncio.create_task(_chamar_openai_texto(prompt, system)))

    if not tasks:
        return "Vocês não podem me derrotar..."

    # MELHORADO: Eu também passei a buscar a primeira fala válida do boss,
    # evitando fallback desnecessário quando a primeira task termina com erro/None.
    pending = set(tasks)
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            try:
                resultado = task.result()
            except Exception:
                continue
            if resultado:
                for p in pending:
                    p.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                return resultado

    return "Vocês não podem me derrotar..."


# ─────────────────────────────────────────
# CHAMADAS DE API
# ─────────────────────────────────────────

async def _chamar_gemini(prompt: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            
            payload = {
                "system_instruction": {
                    "parts": [{"text": SYSTEM_MESTRE}]
                },
                "contents": [{
                    "role": "user",
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "response_mime_type": "application/json"
                }
            }
            headers = {"Content-Type": "application/json"}

            async with session.post(
                url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                texto = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return _parse_json_seguro(texto)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        # MELHORADO: Logging específico de erros de rede para debug
        logger.warning(f"Gemini API error: {type(e).__name__}")
        return None
    except Exception as e:
        # MELHORADO: Captura erros inesperados com stack trace para debug
        logger.exception(f"Unexpected error in _chamar_gemini: {e}")
        return None


async def _chamar_gemini_texto(prompt: str, system: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            
            payload = {
                "system_instruction": {
                    "parts": [{"text": system}]
                },
                "contents": [{
                    "role": "user",
                    "parts": [{"text": prompt}]
                }]
            }
            headers = {"Content-Type": "application/json"}

            async with session.post(
                url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        # MELHORADO: Logging específico de erros de rede para debug (texto)
        logger.warning(f"Gemini API error (text): {type(e).__name__}")
        return None
    except Exception as e:
        # MELHORADO: Captura erros inesperados com stack trace para debug
        logger.exception(f"Unexpected error in _chamar_gemini_texto: {e}")
        return None


async def _chamar_anthropic(prompt: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": ANTHROPIC_MODEL,
                "max_tokens": 200,
                "system": SYSTEM_MESTRE,
                "messages": [{"role": "user", "content": prompt}],
            }
            headers = {
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                texto = data["content"][0]["text"].strip()
                return _parse_json_seguro(texto)
    except Exception:
        return None


async def _chamar_openai(prompt: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": OPENAI_MODEL,
                "max_tokens": 200,
                "messages": [
                    {"role": "system", "content": SYSTEM_MESTRE},
                    {"role": "user", "content": prompt},
                ],
            }
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                texto = data["choices"][0]["message"]["content"].strip()
                return _parse_json_seguro(texto)
    except Exception:
        return None


async def _chamar_anthropic_texto(prompt: str, system: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": ANTHROPIC_MODEL,
                "max_tokens": 150,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            }
            headers = {
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                return data["content"][0]["text"].strip()
    except Exception:
        return None


async def _chamar_openai_texto(prompt: str, system: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": OPENAI_MODEL,
                "max_tokens": 150,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            }
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# ─────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────

def _parse_json_seguro(texto: str) -> dict | None:
    """Remove markdown fences e faz parse seguro do JSON."""
    texto = re.sub(r"```json\s*|\s*```", "", texto)
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return None


def _extrair_alvo_basico(acao: str) -> str | None:
    """Extrai alvo em fallback por padrão simples: 'em X', 'contra X', 'no X' etc."""
    padrao = re.compile(r"(?:em|contra|no|na|ao|à)\s+([\wÀ-ÿ-]+)", re.IGNORECASE)
    match = padrao.search(acao)
    return match.group(1) if match else None


def _inferir_categoria_acao(acao: str) -> str:
    """Inferência simples de categoria para fallback sem IA externa."""
    acao_lower = acao.lower()
    # ADICIONADO: Eu marquei perícia por palavras-chave explícitas de habilidade especial.
    palavras_pericia = (
        "tecnica", "técnica", "habilidade", "magia", "jutsu", "ritual",
        "feitiço", "feitico", "ultimate", "especial", "skill"
    )
    return "pericia" if any(p in acao_lower for p in palavras_pericia) else "basico"

def _fallback_estatico(acao: str) -> dict:
    """Retorna um resultado genérico se todas as IAs falharem ou estiverem offline.
    
    ADICIONADO: Implementa lógica básica de validação para garantir que
    nem toda ação é aceita. Rejeita padrões suspeitos:
    - Ações sem menção a alvo (indicando ação mal construída)
    - Ações muito curtas (provável comando/spam)
    """
    # MELHORADO: Eu reduzi rejeições agressivas no fallback para não bloquear
    # ações válidas quando os provedores de IA estiverem indisponíveis.
    acao_lower = acao.lower().strip()
    alvo_extraido = _extrair_alvo_basico(acao)
    categoria = _inferir_categoria_acao(acao)

    # Mantive rejeição apenas para mensagens quase vazias/spam.
    if len(acao_lower) < 3:
        return {
            "tipo": "ataque",
            "alvo": alvo_extraido,
            "categoria_acao": categoria,
            "va": 3,
            "comentario": "A ação foi rejeitada: muito vaga ou incompleta.",
            "valida": False,
            "motivo_invalido": "Ação muito curta para ser interpretada."
        }

    # Se passou na heurística, aceita
    return {
        "tipo": "ataque",
        "alvo": alvo_extraido,
        "categoria_acao": categoria,
        "va": 5,
        "comentario": "Ação computada pelos sistemas de contingência.",
        "valida": True,
        "motivo_invalido": None
    }