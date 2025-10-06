import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Callable, Optional, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
import logging

logger = logging.getLogger(__name__)

class TimerInfo:
    def __init__(self, id: str, name: str, created_at: datetime, 
                 timer_type: str, target_time: datetime = None, 
                 duration: timedelta = None):
        self.id = id
        self.name = name
        self.created_at = created_at
        self.timer_type = timer_type  # 'timer' or 'alarm'
        self.target_time = target_time
        self.duration = duration
        self.is_active = True
    
    def get_remaining_time(self) -> str:
        """Calculate and format remaining time"""
        if not self.is_active:
            return "Expired"
        
        now = datetime.now()
        if self.target_time:
            remaining = self.target_time - now
            if remaining.total_seconds() <= 0:
                return "Expired"
            return self._format_timedelta(remaining)
        
        return "Unknown"
    
    def _format_timedelta(self, td: timedelta) -> str:
        """Format timedelta for display"""
        total_seconds = int(td.total_seconds())
        if total_seconds <= 0:
            return "Expired"
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert timer info to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.timer_type,
            "created_at": self.created_at.isoformat(),
            "target_time": self.target_time.isoformat() if self.target_time else None,
            "duration": str(self.duration) if self.duration else None,
            "remaining_time": self.get_remaining_time(),
            "is_active": self.is_active
        }

class SchedulerManager:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.active_timers: Dict[str, TimerInfo] = {}
        self.callbacks: Dict[str, Callable] = {}
        self._setup_event_listeners()
        
    def _setup_event_listeners(self):
        """Setup event listeners for scheduler events"""
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self._job_missed, EVENT_JOB_MISSED)
    
    async def start(self):
        """Start the scheduler"""
        try:
            self.scheduler.start()
            logger.info("Scheduler started successfully")
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown the scheduler"""
        try:
            self.scheduler.shutdown(wait=True)
            logger.info("Scheduler shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")
    
    async def create_timer(self, duration: timedelta, name: str = "Timer", 
                          callback: Callable = None) -> str:
        """Create a countdown timer"""
        timer_id = str(uuid.uuid4())
        target_time = datetime.now() + duration
        
        timer_info = TimerInfo(
            id=timer_id,
            name=name,
            created_at=datetime.now(),
            timer_type="timer",
            target_time=target_time,
            duration=duration
        )
        
        self.active_timers[timer_id] = timer_info
        if callback:
            self.callbacks[timer_id] = callback
        
        try:
            self.scheduler.add_job(
                func=self._timer_expired,
                args=[timer_id],
                trigger=DateTrigger(run_date=target_time),
                id=timer_id,
                name=f"Timer: {name}",
                misfire_grace_time=30
            )
            
            logger.info(f"Timer created: {name} ({timer_id}) for {duration}")
            return timer_id
            
        except Exception as e:
            if timer_id in self.active_timers:
                del self.active_timers[timer_id]
            if timer_id in self.callbacks:
                del self.callbacks[timer_id]
            logger.error(f"Error creating timer: {e}")
            raise
    
    async def create_alarm(self, target_time: datetime, name: str = "Alarm", 
                          callback: Callable = None) -> str:
        """Create an alarm for a specific time"""
        alarm_id = str(uuid.uuid4())
        
        alarm_info = TimerInfo(
            id=alarm_id,
            name=name,
            created_at=datetime.now(),
            timer_type="alarm",
            target_time=target_time
        )
        
        self.active_timers[alarm_id] = alarm_info
        if callback:
            self.callbacks[alarm_id] = callback
        
        try:
            self.scheduler.add_job(
                func=self._alarm_triggered,
                args=[alarm_id],
                trigger=DateTrigger(run_date=target_time),
                id=alarm_id,
                name=f"Alarm: {name}",
                misfire_grace_time=60
            )
            
            logger.info(f"Alarm created: {name} ({alarm_id}) for {target_time}")
            return alarm_id
            
        except Exception as e:
            if alarm_id in self.active_timers:
                del self.active_timers[alarm_id]
            if alarm_id in self.callbacks:
                del self.callbacks[alarm_id]
            logger.error(f"Error creating alarm: {e}")
            raise
    
    async def cancel_timer(self, timer_id: str) -> bool:
        """Cancel a specific timer or alarm"""
        try:
            if self.scheduler.get_job(timer_id):
                self.scheduler.remove_job(timer_id)
            
            if timer_id in self.active_timers:
                timer_info = self.active_timers[timer_id]
                timer_info.is_active = False
                del self.active_timers[timer_id]
                logger.info(f"Cancelled {timer_info.timer_type}: {timer_info.name} ({timer_id})")
            
            if timer_id in self.callbacks:
                del self.callbacks[timer_id]
            
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling timer {timer_id}: {e}")
            return False
    
    async def cancel_all_timers(self) -> int:
        """Cancel all active timers and alarms"""
        cancelled_count = 0
        timer_ids = list(self.active_timers.keys())
        
        for timer_id in timer_ids:
            if await self.cancel_timer(timer_id):
                cancelled_count += 1
        
        logger.info(f"Cancelled {cancelled_count} timers/alarms")
        return cancelled_count
    
    async def get_active_timers(self) -> List[Dict[str, Any]]:
        """Get list of active timers and alarms"""
        await self._cleanup_expired_timers()
        return [timer.to_dict() for timer in self.active_timers.values()]
    
    async def _cleanup_expired_timers(self):
        """Remove expired timers from active list"""
        now = datetime.now()
        expired_ids = []
        
        for timer_id, timer_info in self.active_timers.items():
            if (timer_info.target_time and 
                timer_info.target_time <= now and 
                not self.scheduler.get_job(timer_id)):
                expired_ids.append(timer_id)
        
        for timer_id in expired_ids:
            if timer_id in self.active_timers:
                del self.active_timers[timer_id]
            if timer_id in self.callbacks:
                del self.callbacks[timer_id]
    
    async def _timer_expired(self, timer_id: str):
        """Handle timer expiration"""
        try:
            timer_info = self.active_timers.get(timer_id)
            if not timer_info:
                logger.warning(f"Timer {timer_id} not found in active timers")
                return
            
            logger.info(f"Timer expired: {timer_info.name} ({timer_id})")
            
            timer_info.is_active = False
            
            if timer_id in self.callbacks:
                callback = self.callbacks[timer_id]
                if asyncio.iscoroutinefunction(callback):
                    await callback(timer_info.to_dict())
                else:
                    callback(timer_info.to_dict())
            
            if timer_id in self.active_timers:
                del self.active_timers[timer_id]
            if timer_id in self.callbacks:
                del self.callbacks[timer_id]
                
        except Exception as e:
            logger.error(f"Error handling timer expiration for {timer_id}: {e}")
    
    async def _alarm_triggered(self, alarm_id: str):
        """Handle alarm trigger"""
        try:
            alarm_info = self.active_timers.get(alarm_id)
            if not alarm_info:
                logger.warning(f"Alarm {alarm_id} not found in active timers")
                return
            
            logger.info(f"Alarm triggered: {alarm_info.name} ({alarm_id})")
            
            alarm_info.is_active = False
            
            if alarm_id in self.callbacks:
                callback = self.callbacks[alarm_id]
                if asyncio.iscoroutinefunction(callback):
                    await callback(alarm_info.to_dict())
                else:
                    callback(alarm_info.to_dict())
            
            if alarm_id in self.active_timers:
                del self.active_timers[alarm_id]
            if alarm_id in self.callbacks:
                del self.callbacks[alarm_id]
                
        except Exception as e:
            logger.error(f"Error handling alarm trigger for {alarm_id}: {e}")
    
    def _job_executed(self, event):
        """Handle job execution events"""
        logger.debug(f"Job executed: {event.job_id}")
    
    def _job_error(self, event):
        """Handle job error events"""
        logger.error(f"Job error: {event.job_id} - {event.exception}")
    
    def _job_missed(self, event):
        """Handle missed job events"""
        logger.warning(f"Job missed: {event.job_id}")
        
        try:
            if event.job_id in self.active_timers:
                timer_info = self.active_timers[event.job_id]
                logger.info(f"Attempting to trigger missed {timer_info.timer_type}: {timer_info.name}")
                
                if timer_info.timer_type == "timer":
                    asyncio.create_task(self._timer_expired(event.job_id))
                else:
                    asyncio.create_task(self._alarm_triggered(event.job_id))
                    
        except Exception as e:
            logger.error(f"Error handling missed job {event.job_id}: {e}")