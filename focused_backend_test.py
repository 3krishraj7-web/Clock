#!/usr/bin/env python3
"""
Focused Backend Test for AI Clock - Testing specific issues
"""

import asyncio
import json
import requests
import websockets
import sys
from datetime import datetime

# Test configuration
BACKEND_URL = "https://timemate-9.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"
WS_URL = f"wss://timemate-9.preview.emergentagent.com/ws"

async def test_websocket_direct():
    """Test WebSocket connection directly"""
    print("Testing WebSocket connection...")
    
    try:
        # Connect to WebSocket
        websocket = await websockets.connect(WS_URL)
        print("✅ WebSocket connected successfully")
        
        # Test voice command
        command = {
            "type": "voice_command",
            "command": "set timer for 30 seconds"
        }
        
        print(f"Sending command: {command}")
        await websocket.send(json.dumps(command))
        
        # Wait for response with longer timeout
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=15)
            data = json.loads(response)
            print(f"Received response: {data}")
            
            if data.get("type") == "command_processed":
                print("✅ Voice command processed successfully")
                return True
            else:
                print(f"❌ Unexpected response type: {data.get('type')}")
                return False
                
        except asyncio.TimeoutError:
            print("❌ Timeout waiting for WebSocket response")
            return False
        finally:
            await websocket.close()
            
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        return False

def test_mongodb_issue():
    """Test the MongoDB ObjectId serialization issue"""
    print("\nTesting MongoDB serialization issue...")
    
    try:
        # First upload a ringtone
        test_audio_data = b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x08\x00\x00' + b'\x00\x00' * 100
        
        files = {
            'file': ('test.wav', test_audio_data, 'audio/wav')
        }
        
        upload_response = requests.post(f"{API_BASE}/ringtones", files=files, timeout=10)
        
        if upload_response.status_code == 200:
            print("✅ Ringtone uploaded successfully")
            
            # Now try to list ringtones
            list_response = requests.get(f"{API_BASE}/ringtones", timeout=10)
            
            if list_response.status_code == 200:
                data = list_response.json()
                print(f"✅ Ringtones listed successfully: {len(data.get('ringtones', []))} items")
                
                # Clean up - delete the test ringtone
                if data.get('ringtones'):
                    for ringtone in data['ringtones']:
                        if 'id' in ringtone:
                            delete_response = requests.delete(f"{API_BASE}/ringtones/{ringtone['id']}", timeout=10)
                            if delete_response.status_code == 200:
                                print("✅ Test ringtone cleaned up")
                            break
                
                return True
            else:
                print(f"❌ Failed to list ringtones: HTTP {list_response.status_code}")
                print(f"Response: {list_response.text}")
                return False
        else:
            print(f"❌ Failed to upload ringtone: HTTP {upload_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ MongoDB test error: {e}")
        return False

def test_speech_processing():
    """Test speech processing functionality"""
    print("\nTesting speech processing...")
    
    try:
        sys.path.append('/app/backend')
        from speech_processor import SpeechProcessor
        
        sp = SpeechProcessor()
        
        # Test timer command
        result = sp.process_command("set timer for 5 minutes")
        if result.get("success") and result.get("action") == "set_timer":
            print("✅ Timer command processed successfully")
            timer_success = True
        else:
            print(f"❌ Timer command failed: {result}")
            timer_success = False
        
        # Test alarm command
        result = sp.process_command("set alarm for 7 AM")
        if result.get("success") and result.get("action") == "set_alarm":
            print("✅ Alarm command processed successfully")
            alarm_success = True
        else:
            print(f"❌ Alarm command failed: {result}")
            alarm_success = False
        
        # Test list command
        result = sp.process_command("list timers")
        if result.get("success") and result.get("action") == "list_timers":
            print("✅ List command processed successfully")
            list_success = True
        else:
            print(f"❌ List command failed: {result}")
            list_success = False
        
        return timer_success and alarm_success and list_success
        
    except Exception as e:
        print(f"❌ Speech processing error: {e}")
        return False

async def main():
    """Main test execution"""
    print("AI Clock Focused Backend Tests")
    print("=" * 50)
    
    results = []
    
    # Test speech processing
    speech_result = test_speech_processing()
    results.append(("Speech Processing", speech_result))
    
    # Test MongoDB issue
    mongodb_result = test_mongodb_issue()
    results.append(("MongoDB Serialization", mongodb_result))
    
    # Test WebSocket
    websocket_result = await test_websocket_direct()
    results.append(("WebSocket Communication", websocket_result))
    
    # Print summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)}")
    
    return passed == len(results)

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)