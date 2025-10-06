from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
import os
import logging
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timedelta, timezone
import json
import asyncio
from contextlib import asynccontextmanager
import base64

# Import our custom modules
from speech_processor import SpeechProcessor
from scheduler_manager import SchedulerManager

# Setup
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_sessions: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if session_id:
            self.user_sessions[session_id] = websocket
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, session_id: str = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if session_id and session_id in self.user_sessions:
            del self.user_sessions[session_id]
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                disconnected.append(connection)
        
        for connection in disconnected:
            if connection in self.active_connections:
                self.active_connections.remove(connection)

# Global instances
manager = ConnectionManager()
speech_processor = None
scheduler_manager = None

# Pydantic Models
class WorldCityTime(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    city: str
    country: str
    timezone: str
    current_time: str

class Ringtone(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    file_data: str  # base64 encoded
    file_type: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RingtoneCreate(BaseModel):
    name: str
    file_data: str
    file_type: str

class Timer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    duration: timedelta
    target_time: datetime
    is_active: bool = True
    ringtone_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Alarm(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    target_time: datetime
    is_active: bool = True
    ringtone_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global speech_processor, scheduler_manager
    speech_processor = SpeechProcessor()
    scheduler_manager = SchedulerManager()
    await scheduler_manager.start()
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    if scheduler_manager:
        await scheduler_manager.shutdown()
    logger.info("Application shutdown complete")

# Create the main app
app = FastAPI(
    title="AI Clock API",
    description="Voice-controlled AI clock with world time, alarms, timers and custom ringtones",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploads
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# World time cities data
WORLD_CITIES = [
    {"city": "New York", "country": "USA", "timezone": "America/New_York"},
    {"city": "London", "country": "UK", "timezone": "Europe/London"},
    {"city": "Tokyo", "country": "Japan", "timezone": "Asia/Tokyo"},
    {"city": "Dubai", "country": "UAE", "timezone": "Asia/Dubai"},
    {"city": "Sydney", "country": "Australia", "timezone": "Australia/Sydney"},
    {"city": "Paris", "country": "France", "timezone": "Europe/Paris"},
    {"city": "Singapore", "country": "Singapore", "timezone": "Asia/Singapore"},
    {"city": "Los Angeles", "country": "USA", "timezone": "America/Los_Angeles"},
    {"city": "Mumbai", "country": "India", "timezone": "Asia/Kolkata"},
    {"city": "Berlin", "country": "Germany", "timezone": "Europe/Berlin"},
    {"city": "Beijing", "country": "China", "timezone": "Asia/Shanghai"},
    {"city": "Moscow", "country": "Russia", "timezone": "Europe/Moscow"}
]

# API Routes
@app.get("/api/world-time")
async def get_world_time():
    """Get current time for major world cities"""
    import pytz
    world_times = []
    
    for city_data in WORLD_CITIES:
        try:
            tz = pytz.timezone(city_data["timezone"])
            current_time = datetime.now(tz)
            world_times.append({
                "city": city_data["city"],
                "country": city_data["country"],
                "timezone": city_data["timezone"],
                "current_time": current_time.strftime("%H:%M:%S"),
                "date": current_time.strftime("%Y-%m-%d"),
                "day": current_time.strftime("%A")
            })
        except Exception as e:
            logger.error(f"Error getting time for {city_data['city']}: {e}")
            
    return {"world_times": world_times}

@app.post("/api/ringtones")
async def upload_ringtone(file: UploadFile = File(...)):
    """Upload custom ringtone file"""
    try:
        # Validate file type
        allowed_types = ["audio/mpeg", "audio/wav", "audio/mp3", "audio/ogg"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Invalid file type. Only audio files are allowed.")
        
        # Read and encode file
        file_content = await file.read()
        file_data = base64.b64encode(file_content).decode('utf-8')
        
        ringtone = Ringtone(
            name=file.filename.split('.')[0],
            file_data=file_data,
            file_type=file.content_type
        )
        
        # Save to database
        await db.ringtones.insert_one(ringtone.dict())
        
        return {"message": "Ringtone uploaded successfully", "ringtone_id": ringtone.id}
        
    except Exception as e:
        logger.error(f"Error uploading ringtone: {e}")
        raise HTTPException(status_code=500, detail="Error uploading ringtone")

@app.get("/api/ringtones")
async def get_ringtones():
    """Get all uploaded ringtones"""
    try:
        ringtones = await db.ringtones.find({}, {"_id": 0, "file_data": 0}).to_list(100)
        return {"ringtones": ringtones}
    except Exception as e:
        logger.error(f"Error getting ringtones: {e}")
        return {"ringtones": []}

@app.get("/api/ringtones/{ringtone_id}")
async def get_ringtone_audio(ringtone_id: str):
    """Get ringtone audio data"""
    try:
        ringtone = await db.ringtones.find_one({"id": ringtone_id})
        if not ringtone:
            raise HTTPException(status_code=404, detail="Ringtone not found")
        
        return {
            "id": ringtone["id"],
            "name": ringtone["name"],
            "file_data": ringtone["file_data"],
            "file_type": ringtone["file_type"]
        }
    except Exception as e:
        logger.error(f"Error getting ringtone audio: {e}")
        raise HTTPException(status_code=500, detail="Error getting ringtone")

@app.delete("/api/ringtones/{ringtone_id}")
async def delete_ringtone(ringtone_id: str):
    """Delete a ringtone"""
    try:
        result = await db.ringtones.delete_one({"id": ringtone_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Ringtone not found")
        
        return {"message": "Ringtone deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting ringtone: {e}")
        raise HTTPException(status_code=500, detail="Error deleting ringtone")

@app.get("/api/timers")
async def get_timers():
    """Get active timers and alarms"""
    if scheduler_manager:
        return {"timers": await scheduler_manager.get_active_timers()}
    return {"timers": []}

@app.delete("/api/timers/{timer_id}")
async def cancel_timer(timer_id: str):
    """Cancel a specific timer"""
    if scheduler_manager:
        success = await scheduler_manager.cancel_timer(timer_id)
        if success:
            return {"message": "Timer cancelled", "timer_id": timer_id}
    
    raise HTTPException(status_code=404, detail="Timer not found")

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time voice command processing"""
    session_id = None
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "voice_command":
                await process_voice_command(message, websocket)
            elif message.get("type") == "cancel_timer":
                await cancel_timer_command(message, websocket)
            elif message.get("type") == "get_timers":
                await send_timer_list(websocket)
            else:
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Unknown command type"
                }, websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.send_personal_message({
            "type": "error",
            "message": "Server error occurred"
        }, websocket)

async def process_voice_command(message: dict, websocket: WebSocket):
    """Process voice commands using natural language processing"""
    try:
        command_text = message.get("command", "").strip()
        if not command_text:
            await manager.send_personal_message({
                "type": "error",
                "message": "Empty command received"
            }, websocket)
            return

        result = speech_processor.process_command(command_text)
        
        if result["success"]:
            if result["action"] == "set_timer":
                timer_id = await scheduler_manager.create_timer(
                    duration=result["duration"],
                    name=result.get("name", "Timer"),
                    callback=timer_expired_callback
                )
                
                await manager.send_personal_message({
                    "type": "command_processed",
                    "message": f"Timer set for {result['duration_text']}",
                    "timer_id": timer_id,
                    "timers": await scheduler_manager.get_active_timers()
                }, websocket)
                
            elif result["action"] == "set_alarm":
                alarm_id = await scheduler_manager.create_alarm(
                    target_time=result["target_time"],
                    name=result.get("name", "Alarm"),
                    callback=alarm_triggered_callback
                )
                
                await manager.send_personal_message({
                    "type": "command_processed",
                    "message": f"Alarm set for {result['time_text']}",
                    "alarm_id": alarm_id,
                    "timers": await scheduler_manager.get_active_timers()
                }, websocket)
                
            elif result["action"] == "cancel_all":
                cancelled_count = await scheduler_manager.cancel_all_timers()
                await manager.send_personal_message({
                    "type": "command_processed",
                    "message": f"Cancelled {cancelled_count} timer(s)",
                    "timers": []
                }, websocket)
                
            elif result["action"] == "list_timers":
                await send_timer_list(websocket)
                
        else:
            await manager.send_personal_message({
                "type": "error",
                "message": result.get("error", "Could not understand command")
            }, websocket)
            
    except Exception as e:
        logger.error(f"Error processing voice command: {e}")
        await manager.send_personal_message({
            "type": "error",
            "message": "Error processing command"
        }, websocket)

async def cancel_timer_command(message: dict, websocket: WebSocket):
    """Handle timer cancellation requests"""
    try:
        timer_id = message.get("timer_id")
        if not timer_id:
            await manager.send_personal_message({
                "type": "error",
                "message": "Timer ID required"
            }, websocket)
            return

        success = await scheduler_manager.cancel_timer(timer_id)
        if success:
            await manager.send_personal_message({
                "type": "command_processed",
                "message": "Timer cancelled",
                "timers": await scheduler_manager.get_active_timers()
            }, websocket)
        else:
            await manager.send_personal_message({
                "type": "error",
                "message": "Timer not found or already completed"
            }, websocket)
            
    except Exception as e:
        logger.error(f"Error cancelling timer: {e}")

async def send_timer_list(websocket: WebSocket):
    """Send current timer list to client"""
    try:
        timers = await scheduler_manager.get_active_timers()
        await manager.send_personal_message({
            "type": "timer_update",
            "timers": timers
        }, websocket)
    except Exception as e:
        logger.error(f"Error sending timer list: {e}")

async def timer_expired_callback(timer_info: dict):
    """Callback function when timer expires"""
    await manager.broadcast({
        "type": "timer_expired",
        "message": f"Timer '{timer_info['name']}' has expired!",
        "timer_info": timer_info
    })

async def alarm_triggered_callback(alarm_info: dict):
    """Callback function when alarm triggers"""
    await manager.broadcast({
        "type": "alarm_triggered",
        "message": f"Alarm '{alarm_info['name']}' is ringing!",
        "alarm_info": alarm_info
    })

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_connections": len(manager.active_connections) if manager else 0
    }

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# Add pytz import at the top
import pytz

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)