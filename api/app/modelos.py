"""Formato dos dados que entram e saem da API.

`extra="forbid"`: campos desconhecidos (por exemplo psicologo_id) são recusados com erro 422.
"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

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
