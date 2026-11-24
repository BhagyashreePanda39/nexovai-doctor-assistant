from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from loguru import logger
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

from app.voice.pipeline import missing_voice_settings, run_voice_pipeline


router = APIRouter(prefix="/api")
webrtc_handler = SmallWebRTCRequestHandler()


@router.post("/offer", tags=["voice"])
async def handle_webrtc_offer(
    request: SmallWebRTCRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Create or renegotiate a browser SmallWebRTC voice connection."""
    missing = missing_voice_settings()
    if missing:
        logger.error("Voice connection requested with missing settings: {}", missing)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Voice service is not configured. Set: {', '.join(missing)}.",
        )

    async def start_pipeline(connection: SmallWebRTCConnection) -> None:
        background_tasks.add_task(run_voice_pipeline, connection)

    return await webrtc_handler.handle_web_request(
        request=request,
        webrtc_connection_callback=start_pipeline,
    )


@router.patch("/offer", tags=["voice"])
async def handle_ice_candidates(request: SmallWebRTCPatchRequest) -> dict[str, str]:
    """Apply browser ICE candidate updates for an existing voice connection."""
    await webrtc_handler.handle_patch_request(request)
    return {"status": "success"}


async def close_voice_connections() -> None:
    await webrtc_handler.close()
