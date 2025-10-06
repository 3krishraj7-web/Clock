import spacy
import re
from datetime import datetime, timedelta, timezone
from dateutil import parser as date_parser
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SpeechProcessor:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error("spaCy English model not found. Install with: python -m spacy download en_core_web_sm")
            raise
            
        self.time_patterns = self._compile_time_patterns()
        self.command_patterns = self._compile_command_patterns()
        
    def _compile_time_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regular expressions for time parsing"""
        return {
            # Duration patterns (for timers)
            'duration_full': re.compile(r'(\d+)\s*(hour|hr|h)s?\s*(?:and\s*)?(?:(\d+)\s*(minute|min|m)s?)?', re.IGNORECASE),
            'duration_minutes': re.compile(r'(\d+)\s*(minute|min|m)s?', re.IGNORECASE),
            'duration_seconds': re.compile(r'(\d+)\s*(second|sec|s)s?', re.IGNORECASE),
            
            # Time patterns (for alarms)
            'time_12h': re.compile(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)', re.IGNORECASE),
            'time_24h': re.compile(r'(\d{1,2}):(\d{2})', re.IGNORECASE),
            'time_simple': re.compile(r'(\d{1,2})\s*o\'?clock', re.IGNORECASE),
            
            # Relative time patterns
            'relative_time': re.compile(r'in\s+(\d+)\s*(hour|minute|second|hr|min|sec|h|m|s)s?', re.IGNORECASE),
        }
    
    def _compile_command_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regular expressions for command recognition"""
        return {
            'set_timer': re.compile(r'\b(set|start|create|make)\s+(a\s+)?(timer|countdown)', re.IGNORECASE),
            'set_alarm': re.compile(r'\b(set|create|make)\s+(an?\s+)?(alarm|wake)', re.IGNORECASE),
            'cancel': re.compile(r'\b(cancel|stop|delete|remove|clear)', re.IGNORECASE),
            'list': re.compile(r'\b(list|show|display|what|check)\s+(timer|alarm)', re.IGNORECASE),
            'cancel_all': re.compile(r'\b(cancel|stop|clear)\s+(all|everything)', re.IGNORECASE),
        }
    
    def process_command(self, text: str) -> Dict[str, Any]:
        """Main method to process voice commands"""
        try:
            text = text.strip().lower()
            
            # Use spaCy for initial processing
            doc = self.nlp(text)
            
            # Extract entities and analyze sentence structure
            entities = self._extract_entities(doc)
            intent = self._classify_intent(text, entities)
            
            if intent == "set_timer":
                return self._process_timer_command(text, entities)
            elif intent == "set_alarm":
                return self._process_alarm_command(text, entities)
            elif intent == "cancel":
                return self._process_cancel_command(text, entities)
            elif intent == "list":
                return {"success": True, "action": "list_timers"}
            else:
                return {
                    "success": False,
                    "error": "Could not understand the command. Try saying 'set timer for 5 minutes' or 'set alarm for 7 AM'"
                }
                
        except Exception as e:
            logger.error(f"Error processing command '{text}': {e}")
            return {"success": False, "error": "Error processing command"}
    
    def _extract_entities(self, doc) -> Dict[str, Any]:
        """Extract relevant entities from spaCy document"""
        entities = {
            'numbers': [],
            'times': [],
            'durations': [],
            'dates': []
        }
        
        for ent in doc.ents:
            if ent.label_ in ["CARDINAL", "QUANTITY"]:
                try:
                    entities['numbers'].append(int(ent.text))
                except ValueError:
                    pass
            elif ent.label_ == "TIME":
                entities['times'].append(ent.text)
            elif ent.label_ == "DATE":
                entities['dates'].append(ent.text)
        
        for token in doc:
            if token.like_num:
                try:
                    entities['numbers'].append(int(token.text))
                except ValueError:
                    pass
        
        return entities
    
    def _classify_intent(self, text: str, entities: Dict[str, Any]) -> str:
        """Classify the intent of the command"""
        for intent, pattern in self.command_patterns.items():
            if pattern.search(text):
                return intent
                
        # Fallback: look for keywords
        if any(word in text for word in ['timer', 'countdown']):
            return 'set_timer'
        elif any(word in text for word in ['alarm', 'wake']):
            return 'set_alarm'
        elif any(word in text for word in ['cancel', 'stop', 'clear']):
            return 'cancel'
        elif any(word in text for word in ['list', 'show', 'what']):
            return 'list'
            
        return 'unknown'
    
    def _process_timer_command(self, text: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Process timer setting commands"""
        duration = self._extract_duration(text)
        
        if duration is None:
            return {
                "success": False,
                "error": "Could not understand the duration. Try saying '5 minutes' or '1 hour and 30 minutes'"
            }
        
        name = self._extract_timer_name(text)
        
        return {
            "success": True,
            "action": "set_timer",
            "duration": duration,
            "duration_text": self._format_duration(duration),
            "name": name
        }
    
    def _process_alarm_command(self, text: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Process alarm setting commands"""
        target_time = self._extract_alarm_time(text)
        
        if target_time is None:
            return {
                "success": False,
                "error": "Could not understand the time. Try saying '7 AM' or '19:30' or '7:30 PM'"
            }
        
        name = self._extract_alarm_name(text)
        
        return {
            "success": True,
            "action": "set_alarm",
            "target_time": target_time,
            "time_text": target_time.strftime("%I:%M %p"),
            "name": name
        }
    
    def _process_cancel_command(self, text: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Process cancellation commands"""
        if self.command_patterns['cancel_all'].search(text):
            return {"success": True, "action": "cancel_all"}
        else:
            return {"success": True, "action": "cancel_all"}
    
    def _extract_duration(self, text: str) -> Optional[timedelta]:
        """Extract duration from text for timer commands"""
        total_seconds = 0
        
        # Try full hour + minute pattern first
        match = self.time_patterns['duration_full'].search(text)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(3)) if match.group(3) else 0
            return timedelta(hours=hours, minutes=minutes)
        
        # Try minutes pattern
        match = self.time_patterns['duration_minutes'].search(text)
        if match:
            minutes = int(match.group(1))
            return timedelta(minutes=minutes)
        
        # Try seconds pattern
        match = self.time_patterns['duration_seconds'].search(text)
        if match:
            seconds = int(match.group(1))
            return timedelta(seconds=seconds)
        
        # Try relative time patterns
        match = self.time_patterns['relative_time'].search(text)
        if match:
            number = int(match.group(1))
            unit = match.group(2).lower()
            
            if unit in ['hour', 'hr', 'h']:
                return timedelta(hours=number)
            elif unit in ['minute', 'min', 'm']:
                return timedelta(minutes=number)
            elif unit in ['second', 'sec', 's']:
                return timedelta(seconds=number)
        
        return None
    
    def _extract_alarm_time(self, text: str) -> Optional[datetime]:
        """Extract target time from text for alarm commands"""
        now = datetime.now()
        
        # Try 12-hour format
        match = self.time_patterns['time_12h'].search(text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            period = match.group(3).lower()
            
            if period.startswith('p') and hour != 12:
                hour += 12
            elif period.startswith('a') and hour == 12:
                hour = 0
                
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if target <= now:
                target += timedelta(days=1)
                
            return target
        
        # Try 24-hour format
        match = self.time_patterns['time_24h'].search(text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                if target <= now:
                    target += timedelta(days=1)
                    
                return target
        
        # Try simple hour format
        match = self.time_patterns['time_simple'].search(text)
        if match:
            hour = int(match.group(1))
            
            if 6 <= hour <= 11:
                target_hour = hour
            elif 1 <= hour <= 5:
                target_hour = hour + 12
            elif hour == 12:
                target_hour = 12
            else:
                return None
            
            target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
            
            if target <= now:
                target += timedelta(days=1)
                
            return target
        
        return None
    
    def _extract_timer_name(self, text: str) -> str:
        """Extract timer name from command text"""
        name_patterns = [
            r'timer\s+for\s+(\w+)',
            r'(\w+)\s+timer',
            r'called\s+(\w+)',
            r'named\s+(\w+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).capitalize()
        
        return "Timer"
    
    def _extract_alarm_name(self, text: str) -> str:
        """Extract alarm name from command text"""
        name_patterns = [
            r'alarm\s+for\s+(\w+)',
            r'(\w+)\s+alarm',
            r'wake\s+up\s+for\s+(\w+)',
            r'called\s+(\w+)',
            r'named\s+(\w+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).capitalize()
        
        return "Alarm"
    
    def _format_duration(self, duration: timedelta) -> str:
        """Format duration for user-friendly display"""
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0 and hours == 0:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        
        if len(parts) == 0:
            return "0 seconds"
        elif len(parts) == 1:
            return parts[0]
        elif len(parts) == 2:
            return f"{parts[0]} and {parts[1]}"
        else:
            return f"{', '.join(parts[:-1])}, and {parts[-1]}"