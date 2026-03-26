"""
ficha.py — Guaxinim Bot
Modelo de ficha de personagem, parsing e persistência em JSON.

CORREÇÃO: asyncio.Lock() em salvar_ficha() para evitar race condition
em combates simultâneos com múltiplos jogadores.
"""

from __future__ import annotations
import json
import os
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Optional

from config import STATS_VALIDOS, GNOSE_MAX_PADRAO
from elementos import normalizar_elemento

FICHAS_PATH = "fichas.json"

# Lock global — impede que duas corrotinas escrevam simultaneamente
_ficha_lock = asyncio.Lock()


# ─────────────────────────────────────────
# MODELO DE FICHA
# ─────────────────────────────────────────

@dataclass
class FichaPersonagem:
    nome: str
    dono_id: int
    tupper_name: str

    plano: str = "Main"
    elemento_main: str = "Fisico"
    elemento_secundario: Optional[str] = None

    STR: int = 10
    RES: int = 10
    AGI: int = 10
    SEN: int = 10
    VIT: int = 10
    INT: int = 10

    rebirths: int = 0
    hp_max: int = field(init=False)
    hp_atual: int = field(init=False)

    gnose_max: int = GNOSE_MAX_PADRAO
    gnose_atual: int = field(init=False)

    zona: int = 1
    debuffs: list[dict] = field(default_factory=list)
    is_secundario: bool = False

    def __post_init__(self):
        self.hp_max     = self._calcular_hp_max()
        self.hp_atual   = self.hp_max
        self.gnose_atual = self.gnose_max if not self.is_secundario else 0

    # ── HP ──────────────────────────────
    def _calcular_hp_max(self) -> int:
        return (self.VIT * 10) + (self.rebirths * 100)

    def recalcular_hp_max(self):
        novo_max = self._calcular_hp_max()
        if self.hp_max > 0:
            proporcao = self.hp_atual / self.hp_max
            self.hp_atual = int(novo_max * proporcao)
        self.hp_max = novo_max

    def receber_dano(self, dano: int) -> int:
        dano = max(0, dano)
        hp_antes = self.hp_atual
        self.hp_atual = max(0, self.hp_atual - dano)
        return hp_antes - self.hp_atual

    def curar(self, valor: int) -> int:
        hp_antes = self.hp_atual
        self.hp_atual = min(self.hp_max, self.hp_atual + valor)
        return self.hp_atual - hp_antes

    @property
    def hp_percentual(self) -> float:
        return self.hp_atual / self.hp_max if self.hp_max > 0 else 0.0

    @property
    def esta_vivo(self) -> bool:
        return self.hp_atual > 0

    # ── GNOSE ───────────────────────────
    def gastar_gnose(self, custo: int) -> bool:
        if self.is_secundario:
            return True
        if self.gnose_atual < custo:
            return False
        self.gnose_atual -= custo
        return True

    @property
    def gnose_esgotada(self) -> bool:
        return not self.is_secundario and self.gnose_atual <= 0

    # ── DEBUFFS ─────────────────────────
    def adicionar_debuff(self, nome: str, duracao: int, **extra):
        for d in self.debuffs:
            if d["nome"] == nome:
                d["duracao"] = max(d["duracao"], duracao)
                return
        self.debuffs.append({"nome": nome, "duracao": duracao, **extra})

    def tick_debuffs(self) -> list[str]:
        expirados = []
        novos = []
        for d in self.debuffs:
            d["duracao"] -= 1
            if d["duracao"] <= 0:
                expirados.append(d["nome"])
            else:
                novos.append(d)
        self.debuffs = novos
        return expirados

    def tem_debuff(self, nome: str) -> bool:
        return any(d["nome"] == nome for d in self.debuffs)

    # ── SERIALIZAÇÃO ────────────────────
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FichaPersonagem":
        hp_atual     = data.pop("hp_atual", None)
        gnose_atual  = data.pop("gnose_atual", None)
        data.pop("hp_max", None)

        obj = cls(**data)
        if hp_atual is not None:
            obj.hp_atual = hp_atual
        if gnose_atual is not None:
            obj.gnose_atual = gnose_atual
        return obj

    def __repr__(self):
        return (
            f"<Ficha {self.nome} | {self.elemento_main} | "
            f"HP {self.hp_atual}/{self.hp_max} | Gnose {self.gnose_atual}/{self.gnose_max}>"
        )


# ─────────────────────────────────────────
# PERSISTÊNCIA — fichas.json
# ─────────────────────────────────────────

def _carregar_todas() -> dict[str, dict]:
    if not os.path.exists(FICHAS_PATH):
        return {}
    with open(FICHAS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _salvar_todas(dados: dict[str, dict]):
    with open(FICHAS_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def salvar_ficha(ficha: FichaPersonagem):
    """
    Persiste a ficha no JSON.
    CORREÇÃO: usa asyncio.Lock() para serializar escritas concorrentes.
    Como esta função é chamada em contexto síncrono dentro de async handlers,
    a lock é adquirida de forma segura.
    """
    # Tenta adquirir o lock se há um event loop rodando
    try:
        loop = asyncio.get_running_loop()
        # Agenda a escrita segura — não bloqueia o event loop
        loop.create_task(_salvar_ficha_async(ficha))
    except RuntimeError:
        # Sem event loop (testes, CLI) — escrita direta
        dados = _carregar_todas()
        dados[ficha.nome.lower()] = ficha.to_dict()
        _salvar_todas(dados)


async def _salvar_ficha_async(ficha: FichaPersonagem):
    """Versão async de salvar_ficha com lock para concorrência segura."""
    async with _ficha_lock:
        dados = _carregar_todas()
        dados[ficha.nome.lower()] = ficha.to_dict()
        _salvar_todas(dados)


def carregar_ficha_por_nome(nome: str) -> FichaPersonagem | None:
    dados = _carregar_todas()
    raw = dados.get(nome.lower())
    if raw is None:
        return None
    return FichaPersonagem.from_dict(raw)


def carregar_ficha_por_tupper(tupper_name: str) -> FichaPersonagem | None:
    dados = _carregar_todas()
    for raw in dados.values():
        if raw.get("tupper_name", "").lower() == tupper_name.lower():
            return FichaPersonagem.from_dict(raw)
    return None


def carregar_ficha_por_dono(dono_id: int) -> list[FichaPersonagem]:
    dados = _carregar_todas()
    return [
        FichaPersonagem.from_dict(raw)
        for raw in dados.values()
        if raw.get("dono_id") == dono_id
    ]


def deletar_ficha(nome: str) -> bool:
    dados = _carregar_todas()
    key = nome.lower()
    if key not in dados:
        return False
    del dados[key]
    _salvar_todas(dados)
    return True


# ─────────────────────────────────────────
# PARSING DE FICHA
# ─────────────────────────────────────────

class FichaParseError(Exception):
    pass


def criar_ficha_interativa(
    *,
    nome: str,
    dono_id: int,
    tupper_name: str,
    plano: str,
    elemento: str,
    elemento_secundario: str | None,
    str_: int, res: int, agi: int, sen: int, vit: int, int_: int,
    rebirths: int,
    gnose_max: int,
    zona: int,
) -> FichaPersonagem:
    elem_norm = normalizar_elemento(elemento)
    if elem_norm is None:
        raise FichaParseError(
            f"Elemento `{elemento}` não reconhecido. "
            f"Use: Imaginario, Quantum, Raio, Vento, Gelo, Fogo ou Fisico."
        )

    plano_norm = plano.capitalize()
    if plano_norm not in ("Main", "Paranormal"):
        raise FichaParseError("Plano deve ser `Main` ou `Paranormal`.")

    is_sec = plano_norm == "Paranormal"

    elem_sec = None
    if is_sec and elemento_secundario:
        from elementos import get_variante_paranormal
        if get_variante_paranormal(elemento_secundario) is None:
            raise FichaParseError(f"Variante paranormal `{elemento_secundario}` não reconhecida.")
        elem_sec = elemento_secundario

    for stat_nome, val in [("STR", str_), ("RES", res), ("AGI", agi),
                            ("SEN", sen), ("VIT", vit), ("INT", int_)]:
        if val < 1 or val > 99:
            raise FichaParseError(f"Stat `{stat_nome}` deve ser entre 1 e 99.")

    if zona not in (1, 2, 3, 4):
        raise FichaParseError("Zona deve ser 1, 2, 3 ou 4.")

    return FichaPersonagem(
        nome=nome,
        dono_id=dono_id,
        tupper_name=tupper_name,
        plano=plano_norm,
        elemento_main=elem_norm,
        elemento_secundario=elem_sec,
        STR=str_, RES=res, AGI=agi, SEN=sen, VIT=vit, INT=int_,
        rebirths=rebirths,
        gnose_max=gnose_max,
        zona=zona,
        is_secundario=is_sec,
    )
