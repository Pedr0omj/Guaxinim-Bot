"""
brain.py — Guaxinim Bot
IA árbitro narrativo (Mestre): valida ações, gera VA e respostas de boss.
Usa Anthropic Claude, Gemini ou OpenAI via API.
"""

from __future__ import annotations
import os
import re
import json
import aiohttp

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
Você é o Mestre de um RPG de combate estilo Honkai Star Rail / anime shonen.
Sua função: analisar ações de combate e retornar SOMENTE JSON.

Regras de VA (Vantagem de Ação) — valor de 0 a 10:
- 0-2: ação vaga, sem criatividade, sem lógica narrativa
- 3-5: ação razoável, usa o elemento/contexto de forma básica
- 6-8: ação criativa, aproveita bem o elemento e a situação
- 9-10: ação excepcional, cinematográfica, usa fraquezas/buffs do ambiente

Retorne EXCLUSIVAMENTE o JSON abaixo (sem markdown, sem texto extra):
{
    "va": <int 0-10>,
    "comentario": "<string curta e épica de 1 linha sobre a ação>",
    "valida": <true|false>,
    "motivo_invalido": "<string ou null>"
}

Se a ação for fisicamente impossível para o nível de poder/zona do personagem,
defina "valida": false e explique em "motivo_invalido".
""".strip()


async def avaliar_acao(
    nome_personagem: str,
    acao: str,
    elemento: str,
    zona: int,
    alvo: str,
) -> dict:
    """
    Envia a ação para a IA e retorna o dict com VA, comentário e validade.
    Tenta Anthropic primeiro, depois Gemini, depois OpenAI, e fallback estático.
    """
    prompt = (
        f"Personagem: {nome_personagem} (Elemento: {elemento}, Zona {zona})\n"
        f"Alvo: {alvo}\n"
        f"Ação declarada: {acao}"
    )

    if ANTHROPIC_API_KEY:
        resultado = await _chamar_anthropic(prompt)
        if resultado: return resultado

    if GEMINI_API_KEY:
        resultado = await _chamar_gemini(prompt)
        if resultado: return resultado

    if OPENAI_API_KEY:
        resultado = await _chamar_openai(prompt)
        if resultado: return resultado

    return _fallback_estatico(acao)


async def gerar_resposta_boss(
    personalidade: str,
    situacao: str,
    hp_percentual: float,
) -> str:
    """
    Gera uma fala épica do boss baseada em sua personalidade e situação.
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

    if ANTHROPIC_API_KEY:
        resultado = await _chamar_anthropic_texto(prompt, system)
        if resultado: return resultado

    if GEMINI_API_KEY:
        resultado = await _chamar_gemini_texto(prompt, system)
        if resultado: return resultado

    if OPENAI_API_KEY:
        resultado = await _chamar_openai_texto(prompt, system)
        if resultado: return resultado

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
    except Exception:
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
    except Exception:
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

def _fallback_estatico(acao: str) -> dict:
    """Retorna um resultado genérico se todas as IAs falharem."""
    return {
        "va": 5,
        "comentario": "Ação razoável, mas sem brilho.",
        "valida": True,
        "motivo_invalido": None
    }