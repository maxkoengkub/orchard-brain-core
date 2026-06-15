from fastapi import APIRouter, Depends, HTTPException
from database.repository import DatabaseRepository
from api.dependencies import get_repository
from api.schemas import CommandRequest, ConfigurationRequest

router = APIRouter(tags=["Control"])

@router.post("/commands", status_code=202)
async def dispatch_command(
    command: CommandRequest,
    repo: DatabaseRepository = Depends(get_repository)
):
    """
    Queue an actuation command for transmission.
    The Gateway service polls pending commands and dispatches them via LoRa.
    """
    cmd_dict = command.model_dump()
    saved = await repo.save_command(cmd_dict)
    return {"status": "QUEUED", "command_id": saved.command_id}

@router.post("/configuration", status_code=202)
async def push_configuration(
    config: ConfigurationRequest,
    repo: DatabaseRepository = Depends(get_repository)
):
    """
    Queue a configuration update for transmission.
    """
    conf_dict = config.model_dump()
    event = await repo.save_configuration(conf_dict)
    return {"status": "QUEUED", "event_id": event.id}
