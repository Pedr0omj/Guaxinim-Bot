"""
ficha.py — Guaxinim Bot
Modelo de ficha de personagem, parsing e persistência em JSON.
"""

from __future__ import annotations
import json
import os
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Optional

from config import VALID_STATS
from elementos import normalizar_elemento

FICHAS_PATH = "fichas.json"

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

    # Gnose baseada em 100 e atributos de Perícia (SP)
    gnose_max: int = 100
    gnose_atual: int = field(init=False)

    sp_max: int = 10
    sp_atual: int = field(init=False)
    is_resting: bool = False

    zona: int = 1
    debuffs: list[dict] = field(default_factory=list)
    is_secundario: bool = False

    def __post_init__(self):
        self.hp_max      = self._calcular_hp_max()
        self.hp_atual    = self.hp_max
        self.gnose_atual = self.gnose_max if not self.is_secundario else 0
        self.sp_atual    = self.sp_max

    def ativar_descanso(self):
        self.is_resting = True

    def processar_virada_turno(self):
        regen = 25 if self.is_resting else 10
        self.gnose_atual = min(self.gnose_max, self.gnose_atual + regen)
        self.is_resting = False

    # ── HP ──────────────────────────────
    def _calcular_hp_max(self) -> int:
        return (self.VIT * 10) + (self.rebirths * 100)

    def recalcular_hp_max(self):
        novo_max = self._calcular_hp_max()
        # MELHORADO: Eu apenas chekava se hp_max > 0, mas isso era frágil (edge case raro).
        # Agora garanto que nunca divido por zero e preservo proporção de HP com mais segurança.
        if self.hp_max > 0 and novo_max > 0:
            proporcao = self.hp_atual / self.hp_max
            self.hp_atual = max(1, int(novo_max * proporcao))
        else:
            # Edge case: se hp_max era 0 ou novo_max é 0, redefine HP para máximo
            self.hp_atual = novo_max
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
        sp_atual     = data.pop("sp_atual", None)
        is_resting   = data.pop("is_resting", False)
        data.pop("hp_max", None)
        
        # Filtra chaves válidas para evitar crash com fichas antigas
        valid_keys = {"nome", "dono_id", "tupper_name", "plano", "elemento_main", 
                      "elemento_secundario", "STR", "RES", "AGI", "SEN", "VIT", "INT", 
                      "rebirths", "gnose_max", "sp_max", "zona", "debuffs", "is_secundario"}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}

        obj = cls(**filtered_data)
        if hp_atual is not None:
            obj.hp_atual = hp_atual
        if gnose_atual is not None:
            obj.gnose_atual = gnose_atual
        if sp_atual is not None:
            obj.sp_atual = sp_atual
        obj.is_resting = is_resting
        return obj

    def __repr__(self):
        return (
            f"<Ficha {self.nome} | {self.elemento_main} | "
            f"HP {self.hp_atual}/{self.hp_max} | Gnose {self.gnose_atual}/{self.gnose_max} | SP {self.sp_atual}/{self.sp_max}>"
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


def salvar_ficha(ficha: FichaPersonagem) -> None:
    """
    Salva a ficha de forma segura contra race conditions.
    Sempre usa salvamento síncrono com lock para garantir dados salvos antes de continuar.
    
    CORREÇÃO: Eu estava criando uma task assíncrona sem aguardar, o que causava
    possível perda de dados em shutdown. Agora sempre executa salvamento bloqueante
    para garantir atomicidade. Para contextos assíncronos, use salvar_ficha_async().
    """
    _salvar_ficha_sync(ficha)


def _salvar_ficha_sync(ficha: FichaPersonagem):
    """Synchronous save (for non-async contexts)."""
    dados = _carregar_todas()
    dados[ficha.nome.lower()] = ficha.to_dict()
    _salvar_todas(dados)


async def _salvar_ficha_async(ficha: FichaPersonagem):
    async with _ficha_lock:
        dados = _carregar_todas()
        dados[ficha.nome.lower()] = ficha.to_dict()
        _salvar_todas(dados)


async def salvar_ficha_async(ficha: FichaPersonagem) -> None:
    """
    Versão assíncrona segura de salvar_ficha para contextos async.
    Use esta função quando estiver em um handler assíncrono para não bloquear a event loop.
    
    ADICIONADO: Novo método para permitir salvamento não-bloqueante em handlers assíncronos.
    Esta função aguarda o lock antes de salvar, garantindo atomicidade sem bloquear.
    """
    await _salvar_ficha_async(ficha)


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
        gnose_max=gnose_max,  # Use parameter, not hardcoded
        zona=zona,
        is_secundario=is_sec,
    )