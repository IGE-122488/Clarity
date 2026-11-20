from fastapi import APIRouter

from .. import __version__
from ..deps import ClientDep, CurrentUser, SettingsDep
from ..supabase_auth import check_health

router = APIRouter(tags=["estado"])


@router.get("/estado")
async def estado(settings: SettingsDep, client: ClientDep) -> dict:
    """Estado da API: ambiente, versão e ligação ao Supabase. Não devolve dados."""
    ligado = await check_health(client, settings)
    versao = f"{__version__} ({settings.commit})" if settings.commit else __version__
    return {
        "ambiente": settings.app_env,
        "versao": versao,
        "supabase": "ligado" if ligado else "sem ligação",
    }


@router.get("/eu")
async def eu(user: CurrentUser) -> dict:
    """Confirma que a sessão do psicólogo é válida (teste ponta a ponta do login)."""
    return {"id": user.id, "email": user.email}
