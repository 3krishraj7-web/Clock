#!/usr/bin/env python3
"""
Comprehensive Backend Test Suite for AI Clock Application
Tests all API endpoints, WebSocket functionality, and integrations
"""

import asyncio
import json
import base64
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests
import websockets
from io import BytesIO

# Add backend directory to path for imports
sys.path.append('/app/backend')

# Test configuration
BACKEND_URL = "https://timemate-9.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"
WS_URL = f"wss://timemate-9.preview.emergentagent.com/ws"

class AIClockTester:
    def __init__(self):
        self.test_results = {}
        self.websocket = None
        self.test_ringtone_id = None
        
    def log_result(self, test_name, success, message="", details=None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
        self.test_results[test_name] = {
            "success": success,
            "message": message,
            "details": details or {}
        }
    
    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        try:
            response = requests.get(f"{API_BASE}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "status" in data and data["status"] == "healthy":
                    self.log_result("Health Check", True, "Health endpoint working correctly")
                    return True
                else:
                    self.log_result("Health Check", False, f"Invalid health response: {data}")
            else:
                self.log_result("Health Check", False, f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Health Check", False, f"Connection error: {str(e)}")
        
        return False
    
    def test_world_time_endpoint(self):
        """Test /api/world-time endpoint"""
        try:
            response = requests.get(f"{API_BASE}/world-time", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "world_times" in data and isinstance(data["world_times"], list):
                    world_times = data["world_times"]
                    if len(world_times) > 0:
                        # Check structure of first city
                        first_city = world_times[0]
                        required_fields = ["city", "country", "timezone", "current_time", "date", "day"]
                        
                        if all(field in first_city for field in required_fields):
                            self.log_result("World Time API", True, 
                                          f"Retrieved {len(world_times)} cities with correct structure")
                            return True
                        else:
                            missing = [f for f in required_fields if f not in first_city]
                            self.log_result("World Time API", False, f"Missing fields: {missing}")
                    else:
                        self.log_result("World Time API", False, "No cities returned")
                else:
                    self.log_result("World Time API", False, "Invalid response structure")
            else:
                self.log_result("World Time API", False, f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("World Time API", False, f"Error: {str(e)}")
        
        return False
    
    def test_ringtone_upload(self):
        """Test ringtone upload functionality"""
        try:
            # Create a simple test audio file (WAV format)
            test_audio_data = self.create_test_audio_file()
            
            files = {
                'file': ('test_ringtone.wav', BytesIO(test_audio_data), 'audio/wav')
            }
            
            response = requests.post(f"{API_BASE}/ringtones", files=files, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "ringtone_id" in data and "message" in data:
                    self.test_ringtone_id = data["ringtone_id"]
                    self.log_result("Ringtone Upload", True, 
                                  f"Successfully uploaded ringtone: {data['ringtone_id']}")
                    return True
                else:
                    self.log_result("Ringtone Upload", False, f"Invalid response: {data}")
            else:
                self.log_result("Ringtone Upload", False, f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Ringtone Upload", False, f"Error: {str(e)}")
        
        return False
    
    def test_ringtone_list(self):
        """Test getting ringtone list"""
        try:
            response = requests.get(f"{API_BASE}/ringtones", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "ringtones" in data and isinstance(data["ringtones"], list):
                    ringtones = data["ringtones"]
                    self.log_result("Ringtone List", True, 
                                  f"Retrieved {len(ringtones)} ringtones")
                    return True
                else:
                    self.log_result("Ringtone List", False, "Invalid response structure")
            else:
                self.log_result("Ringtone List", False, f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Ringtone List", False, f"Error: {str(e)}")
        
        return False
    
    def test_ringtone_get_audio(self):
        """Test getting specific ringtone audio data"""
        if not self.test_ringtone_id:
            self.log_result("Ringtone Get Audio", False, "No test ringtone ID available")
            return False
            
        try:
            response = requests.get(f"{API_BASE}/ringtones/{self.test_ringtone_id}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["id", "name", "file_data", "file_type"]
                
                if all(field in data for field in required_fields):
                    # Verify base64 data
                    try:
                        base64.b64decode(data["file_data"])
                        self.log_result("Ringtone Get Audio", True, 
                                      f"Successfully retrieved audio data for {data['name']}")
                        return True
                    except Exception:
                        self.log_result("Ringtone Get Audio", False, "Invalid base64 audio data")
                else:
                    missing = [f for f in required_fields if f not in data]
                    self.log_result("Ringtone Get Audio", False, f"Missing fields: {missing}")
            else:
                self.log_result("Ringtone Get Audio", False, f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Ringtone Get Audio", False, f"Error: {str(e)}")
        
        return False
    
    def test_timers_endpoint(self):
        """Test /api/timers endpoint"""
        try:
            response = requests.get(f"{API_BASE}/timers", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "timers" in data and isinstance(data["timers"], list):
                    self.log_result("Timers API", True, 
                                  f"Retrieved {len(data['timers'])} active timers")
                    return True
                else:
                    self.log_result("Timers API", False, "Invalid response structure")
            else:
                self.log_result("Timers API", False, f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Timers API", False, f"Error: {str(e)}")
        
        return False
    
    async def test_websocket_connection(self):
        """Test WebSocket connection"""
        try:
            self.websocket = await websockets.connect(WS_URL)
            self.log_result("WebSocket Connection", True, "Successfully connected to WebSocket")
            return True
            
        except Exception as e:
            self.log_result("WebSocket Connection", False, f"Connection failed: {str(e)}")
            return False
    
    async def test_voice_command_timer(self):
        """Test voice command for setting timer"""
        if not self.websocket:
            self.log_result("Voice Command Timer", False, "No WebSocket connection")
            return False
            
        try:
            # Send timer command
            command = {
                "type": "voice_command",
                "command": "set timer for 2 minutes"
            }
            
            await self.websocket.send(json.dumps(command))
            
            # Wait for response
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            data = json.loads(response)
            
            if data.get("type") == "command_processed" and "timer_id" in data:
                self.log_result("Voice Command Timer", True, 
                              f"Timer created successfully: {data.get('message', '')}")
                return True
            else:
                self.log_result("Voice Command Timer", False, f"Unexpected response: {data}")
                
        except asyncio.TimeoutError:
            self.log_result("Voice Command Timer", False, "Timeout waiting for response")
        except Exception as e:
            self.log_result("Voice Command Timer", False, f"Error: {str(e)}")
        
        return False
    
    async def test_voice_command_alarm(self):
        """Test voice command for setting alarm"""
        if not self.websocket:
            self.log_result("Voice Command Alarm", False, "No WebSocket connection")
            return False
            
        try:
            # Send alarm command for tomorrow 7 AM
            command = {
                "type": "voice_command",
                "command": "set alarm for 7 AM"
            }
            
            await self.websocket.send(json.dumps(command))
            
            # Wait for response
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            data = json.loads(response)
            
            if data.get("type") == "command_processed" and "alarm_id" in data:
                self.log_result("Voice Command Alarm", True, 
                              f"Alarm created successfully: {data.get('message', '')}")
                return True
            else:
                self.log_result("Voice Command Alarm", False, f"Unexpected response: {data}")
                
        except asyncio.TimeoutError:
            self.log_result("Voice Command Alarm", False, "Timeout waiting for response")
        except Exception as e:
            self.log_result("Voice Command Alarm", False, f"Error: {str(e)}")
        
        return False
    
    async def test_voice_command_list_timers(self):
        """Test voice command for listing timers"""
        if not self.websocket:
            self.log_result("Voice Command List", False, "No WebSocket connection")
            return False
            
        try:
            # Send list command
            command = {
                "type": "get_timers"
            }
            
            await self.websocket.send(json.dumps(command))
            
            # Wait for response
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            data = json.loads(response)
            
            if data.get("type") == "timer_update" and "timers" in data:
                timer_count = len(data["timers"])
                self.log_result("Voice Command List", True, 
                              f"Retrieved {timer_count} active timers via WebSocket")
                return True
            else:
                self.log_result("Voice Command List", False, f"Unexpected response: {data}")
                
        except asyncio.TimeoutError:
            self.log_result("Voice Command List", False, "Timeout waiting for response")
        except Exception as e:
            self.log_result("Voice Command List", False, f"Error: {str(e)}")
        
        return False
    
    async def test_voice_command_cancel(self):
        """Test voice command for cancelling timers"""
        if not self.websocket:
            self.log_result("Voice Command Cancel", False, "No WebSocket connection")
            return False
            
        try:
            # Send cancel command
            command = {
                "type": "voice_command",
                "command": "cancel all timers"
            }
            
            await self.websocket.send(json.dumps(command))
            
            # Wait for response
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            data = json.loads(response)
            
            if data.get("type") == "command_processed":
                self.log_result("Voice Command Cancel", True, 
                              f"Cancel command processed: {data.get('message', '')}")
                return True
            else:
                self.log_result("Voice Command Cancel", False, f"Unexpected response: {data}")
                
        except asyncio.TimeoutError:
            self.log_result("Voice Command Cancel", False, "Timeout waiting for response")
        except Exception as e:
            self.log_result("Voice Command Cancel", False, f"Error: {str(e)}")
        
        return False
    
    def test_ringtone_delete(self):
        """Test ringtone deletion"""
        if not self.test_ringtone_id:
            self.log_result("Ringtone Delete", False, "No test ringtone ID available")
            return False
            
        try:
            response = requests.delete(f"{API_BASE}/ringtones/{self.test_ringtone_id}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    self.log_result("Ringtone Delete", True, 
                                  f"Successfully deleted ringtone: {data['message']}")
                    return True
                else:
                    self.log_result("Ringtone Delete", False, f"Invalid response: {data}")
            else:
                self.log_result("Ringtone Delete", False, f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Ringtone Delete", False, f"Error: {str(e)}")
        
        return False
    
    def create_test_audio_file(self):
        """Create a simple test WAV file"""
        # Simple WAV file header + minimal audio data
        wav_header = b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x08\x00\x00'
        # Add some simple audio data (silence)
        audio_data = b'\x00\x00' * 1024  # 1024 samples of silence
        return wav_header + audio_data
    
    async def close_websocket(self):
        """Close WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("AI CLOCK BACKEND TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\nFAILED TESTS:")
            for test_name, result in self.test_results.items():
                if not result["success"]:
                    print(f"  ❌ {test_name}: {result['message']}")
        
        print("\n" + "="*60)
        
        return passed_tests, failed_tests

async def main():
    """Main test execution"""
    print("Starting AI Clock Backend Tests...")
    print(f"Testing backend at: {BACKEND_URL}")
    print("-" * 60)
    
    tester = AIClockTester()
    
    # Test API endpoints
    print("\n🔍 Testing API Endpoints...")
    tester.test_health_endpoint()
    tester.test_world_time_endpoint()
    tester.test_timers_endpoint()
    
    # Test ringtone functionality
    print("\n🎵 Testing Ringtone Management...")
    tester.test_ringtone_upload()
    tester.test_ringtone_list()
    tester.test_ringtone_get_audio()
    
    # Test WebSocket functionality
    print("\n🔌 Testing WebSocket Functionality...")
    ws_connected = await tester.test_websocket_connection()
    
    if ws_connected:
        await tester.test_voice_command_timer()
        await tester.test_voice_command_alarm()
        await tester.test_voice_command_list_timers()
        await tester.test_voice_command_cancel()
        await tester.close_websocket()
    
    # Clean up - delete test ringtone
    print("\n🧹 Cleaning up...")
    tester.test_ringtone_delete()
    
    # Print summary
    passed, failed = tester.print_summary()
    
    return passed, failed

if __name__ == "__main__":
    try:
        passed, failed = asyncio.run(main())
        sys.exit(0 if failed == 0 else 1)
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)