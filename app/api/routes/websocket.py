from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.progress import subscribe_progress


router = APIRouter()

@router.websocket("ws/jobs/{job_id}")
async def job_progress(websocket: WebSocket, job_id: int):
    await websocket.accept()

    try:
        async for event in subscribe_progress(job_id):
            await websocket.send_json(event)
    
    except WebSocketDisconnect:
        print(f"Client disconnected from job {job_id}")