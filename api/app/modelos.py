"""Formato dos dados que entram e saem da API.

`extra="forbid"`: campos desconhecidos (por exemplo psicologo_id) são recusados com erro 422.
"""

from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

Nome = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


def _validar_data_nascimento(valor: date | None) -> date | None:
    if valor is not None and not date(1900, 1, 1) <= valor <= date.today():
        raise ValueError("A data de nascimento tem de estar entre 1900 e hoje.")
    return valor


class PacienteNovo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: Nome
    data_nascimento: date | None = None

    @field_validator("data_nascimento")
    @classmethod
    def validar_data_nascimento(cls, valor: date | None) -> date | None:
        return _validar_data_nascimento(valor)


class PacienteAlteracao(BaseModel):
    """Só os campos enviados são alterados. `ativo: false` arquiva o paciente."""

    model_config = ConfigDict(extra="forbid")

    nome: Nome | None = None
    data_nascimento: date | None = None
    ativo: bool | None = None

    @field_validator("data_nascimento")
    @classmethod
    def validar_data_nascimento(cls, valor: date | None) -> date | None:
        return _validar_data_nascimento(valor)

    @model_validator(mode="after")
    def verificar_campos(self) -> "PacienteAlteracao":
        if not self.model_fields_set:
            raise ValueError("Indique pelo menos um campo a alterar.")
        for campo in ("nome", "ativo"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ficar vazio.")
        return self


class Paciente(BaseModel):
    id: UUID
    nome: str
    data_nascimento: date | None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


# Consultas (agenda)

EstadoConsulta = Literal["agendada", "realizada", "cancelada", "faltou"]
Notas = Annotated[str, StringConstraints(max_length=20000)]
DURACAO_MAXIMA = timedelta(hours=8)


def validar_horario(inicio: datetime, fim: datetime) -> None:
    """Regras comuns a marcar e a remarcar. Lança ValueError com a mensagem para o utilizador."""
    if not 2000 <= inicio.year <= 2100:
        raise ValueError("A data da consulta não é válida.")
    if fim <= inicio:
        raise ValueError("A consulta tem de acabar depois de começar.")
    if fim - inicio > DURACAO_MAXIMA:
        raise ValueError("Uma consulta não pode durar mais de 8 horas.")


class ConsultaNova(BaseModel):
    """`ignorar_sobreposicao: true` marca mesmo que já haja outra consulta nesse horário."""

    model_config = ConfigDict(extra="forbid")

    paciente_id: UUID
    inicio: AwareDatetime
    fim: AwareDatetime
    estado: EstadoConsulta = "agendada"
    notas: Notas | None = None
    ignorar_sobreposicao: bool = False

    @model_validator(mode="after")
    def verificar_horario(self) -> "ConsultaNova":
        validar_horario(self.inicio, self.fim)
        return self


class ConsultaAlteracao(BaseModel):
    """Só os campos enviados são alterados. Remarcar = mudar inicio/fim; cancelar = estado."""

    model_config = ConfigDict(extra="forbid")

    inicio: AwareDatetime | None = None
    fim: AwareDatetime | None = None
    estado: EstadoConsulta | None = None
    notas: Notas | None = None
    ignorar_sobreposicao: bool = False

    @model_validator(mode="after")
    def verificar_campos(self) -> "ConsultaAlteracao":
        if not self.model_fields_set - {"ignorar_sobreposicao"}:
            raise ValueError("Indique pelo menos um campo a alterar.")
        for campo in ("inicio", "fim", "estado"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ficar vazio.")
        return self


class ConsultaAgenda(BaseModel):
    """Consulta como aparece na agenda: sem as notas."""

    id: UUID
    paciente_id: UUID
    inicio: datetime
    fim: datetime
    estado: EstadoConsulta
    criado_em: datetime
    atualizado_em: datetime


class Consulta(ConsultaAgenda):
    notas: str | None


# Briefings (passo 4)

TextoBriefing = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)
]


class BriefingAlteracao(BaseModel):
    """O psicólogo edita o texto e/ou marca o briefing como revisto."""

    model_config = ConfigDict(extra="forbid")

    texto: TextoBriefing | None = None
    revisto: bool | None = None

    @model_validator(mode="after")
    def verificar_campos(self) -> "BriefingAlteracao":
        if not self.model_fields_set:
            raise ValueError("Indique pelo menos um campo a alterar.")
        for campo in ("texto", "revisto"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ficar vazio.")
        return self


class Briefing(BaseModel):
    id: UUID
    consulta_id: UUID
    texto: str
    revisto: bool
    modelo: str
    sessoes_usadas: int
    gerado_em: datetime
    criado_em: datetime
    atualizado_em: datetime
