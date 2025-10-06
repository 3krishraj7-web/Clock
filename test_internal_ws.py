#!/usr/bin/env python3
"""
Test WebSocket on internal port
"""

import asyncio
import json
import websockets

async def test_internal_websocket():
    """Test WebSocket connection on internal port"""
    print("Testing internal WebSocket connection...")
    
    try:
        # Connect to internal WebSocket
        websocket = await websockets.connect("ws://localhost:8001/ws")
        print("✅ Internal WebSocket connected successfully")
        
        # Test voice command
        command = {
            "type": "voice_command",
            "command": "set timer for 10 seconds"
        }
        
        print(f"Sending command: {command}")
        await websocket.send(json.dumps(command))
        
        # Wait for response
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(response)
            print(f"Received response: {data}")
            
            if data.get("type") == "command_processed":
                print("✅ Voice command processed successfully")
                
                # Test getting timers
                timer_command = {"type": "get_timers"}
                await websocket.send(json.dumps(timer_command))
                
                timer_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                timer_data = json.loads(timer_response)
                print(f"Timer list response: {timer_data}")
                
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
        print(f"❌ Internal WebSocket error: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_internal_websocket())
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")