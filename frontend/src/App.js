import React, { useState, useEffect, useRef } from 'react';
import '@/App.css';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// Main Clock Component
const DigitalClock = () => {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="digital-clock">
      <div className="time-display">
        {time.toLocaleTimeString('en-US', { 
          hour12: true, 
          hour: '2-digit', 
          minute: '2-digit', 
          second: '2-digit' 
        })}
      </div>
      <div className="date-display">
        {time.toLocaleDateString('en-US', { 
          weekday: 'long', 
          year: 'numeric', 
          month: 'long', 
          day: 'numeric' 
        })}
      </div>
    </div>
  );
};

// World Time Component
const WorldTime = () => {
  const [worldTimes, setWorldTimes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchWorldTimes = async () => {
      try {
        const response = await axios.get(`${BACKEND_URL}/api/world-time`);
        setWorldTimes(response.data.world_times || []);
      } catch (error) {
        console.error('Error fetching world times:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchWorldTimes();
    const interval = setInterval(fetchWorldTimes, 60000); // Update every minute
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="loading-spinner">Loading world times...</div>;

  return (
    <div className="world-time-container">
      <h3 className="section-title">🌍 World Time</h3>
      <div className="world-time-grid">
        {worldTimes.map((cityTime, index) => (
          <div key={index} className="world-time-card">
            <div className="city-name">{cityTime.city}</div>
            <div className="country-name">{cityTime.country}</div>
            <div className="city-time">{cityTime.current_time}</div>
            <div className="city-date">{cityTime.day}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

// Voice Command Component
const VoiceCommands = ({ onCommandResult }) => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [status, setStatus] = useState('Ready for voice commands');
  const [connected, setConnected] = useState(false);
  const websocketRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    setupWebSocket();
    setupSpeechRecognition();
    return () => {
      if (websocketRef.current) {
        websocketRef.current.close();
      }
    };
  }, []);

  const setupWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host.replace('3000', '8001')}/ws`;
    
    websocketRef.current = new WebSocket(wsUrl);
    
    websocketRef.current.onopen = () => {
      setConnected(true);
      setStatus('Connected to AI voice processor');
    };

    websocketRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleServerResponse(data);
    };

    websocketRef.current.onerror = () => {
      setConnected(false);
      setStatus('Connection error - Please refresh');
    };

    websocketRef.current.onclose = () => {
      setConnected(false);
      setStatus('Disconnected from server');
    };
  };

  const setupSpeechRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      setStatus('Speech recognition not supported in this browser');
      return;
    }

    recognitionRef.current = new SpeechRecognition();
    recognitionRef.current.continuous = false;
    recognitionRef.current.interimResults = true;
    recognitionRef.current.lang = 'en-US';

    recognitionRef.current.onstart = () => {
      setIsListening(true);
      setStatus('🎤 Listening for your command...');
    };

    recognitionRef.current.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      if (finalTranscript) {
        processVoiceCommand(finalTranscript);
        setTranscript(`Command: "${finalTranscript}"`);
      } else if (interimTranscript) {
        setTranscript(`Listening: "${interimTranscript}"`);
      }
    };

    recognitionRef.current.onerror = (event) => {
      setIsListening(false);
      setStatus(`Voice recognition error: ${event.error}`);
    };

    recognitionRef.current.onend = () => {
      setIsListening(false);
    };
  };

  const processVoiceCommand = (command) => {
    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'voice_command',
        command: command,
        timestamp: new Date().toISOString()
      }));
      setStatus('🤖 AI processing your command...');
    } else {
      setStatus('Not connected to server');
    }
  };

  const handleServerResponse = (data) => {
    switch (data.type) {
      case 'command_processed':
        setStatus(`✅ ${data.message}`);
        if (onCommandResult) {
          onCommandResult(data);
        }
        break;
      case 'timer_expired':
        setStatus(`⏰ TIMER ALERT: ${data.message}`);
        playAlarmSound();
        if (onCommandResult) {
          onCommandResult(data);
        }
        break;
      case 'alarm_triggered':
        setStatus(`🔔 ALARM ALERT: ${data.message}`);
        playAlarmSound();
        if (onCommandResult) {
          onCommandResult(data);
        }
        break;
      case 'error':
        setStatus(`❌ ${data.message}`);
        break;
      default:
        console.log('Unknown message type:', data.type);
    }
  };

  const playAlarmSound = () => {
    // Create a simple beep sound
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    
    oscillator.start();
    oscillator.stop(audioContext.currentTime + 1);
  };

  const startListening = async () => {
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      recognitionRef.current?.start();
    } catch (error) {
      setStatus('Microphone access denied');
    }
  };

  const stopListening = () => {
    recognitionRef.current?.stop();
  };

  return (
    <div className="voice-commands">
      <h3 className="section-title">🎤 AI Voice Commands</h3>
      <div className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
        {connected ? '🟢 AI Connected' : '🔴 AI Disconnected'}
      </div>
      
      <div className="voice-controls">
        <button
          className={`voice-button ${isListening ? 'listening' : ''}`}
          onClick={isListening ? stopListening : startListening}
          disabled={!connected}
        >
          {isListening ? '🔴 Stop Listening' : '🎤 Start Voice Command'}
        </button>
      </div>

      <div className="voice-status">
        <p className="status-text">{status}</p>
        {transcript && <p className="transcript">{transcript}</p>}
      </div>

      <div className="voice-examples">
        <h4>Try saying:</h4>
        <ul>
          <li>"Set timer for 5 minutes"</li>
          <li>"Create alarm for 7 AM"</li>
          <li>"Set cooking timer for 25 minutes"</li>
          <li>"Wake me up at 6:30 PM"</li>
          <li>"Cancel all timers"</li>
          <li>"List my timers"</li>
        </ul>
      </div>
    </div>
  );
};

// Timer Management Component
const TimerManager = ({ refreshTrigger }) => {
  const [timers, setTimers] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchTimers();
  }, [refreshTrigger]);

  const fetchTimers = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/timers`);
      setTimers(response.data.timers || []);
    } catch (error) {
      console.error('Error fetching timers:', error);
    } finally {
      setLoading(false);
    }
  };

  const cancelTimer = async (timerId) => {
    try {
      await axios.delete(`${BACKEND_URL}/api/timers/${timerId}`);
      fetchTimers();
    } catch (error) {
      console.error('Error cancelling timer:', error);
    }
  };

  if (loading && timers.length === 0) {
    return <div className="loading-spinner">Loading timers...</div>;
  }

  return (
    <div className="timer-manager">
      <h3 className="section-title">⏰ Active Timers & Alarms</h3>
      {timers.length === 0 ? (
        <div className="no-timers">
          <p>No active timers or alarms</p>
          <p className="help-text">Use voice commands to create timers and alarms</p>
        </div>
      ) : (
        <div className="timer-list">
          {timers.map((timer) => (
            <div key={timer.id} className="timer-card">
              <div className="timer-info">
                <div className="timer-name">
                  {timer.type === 'timer' ? '⏲️' : '⏰'} {timer.name}
                </div>
                <div className="timer-time">
                  {timer.remaining_time}
                </div>
                <div className="timer-target">
                  {timer.type === 'alarm' ? 
                    `Rings at ${new Date(timer.target_time).toLocaleTimeString()}` :
                    `Started ${new Date(timer.created_at).toLocaleTimeString()}`
                  }
                </div>
              </div>
              <button 
                className="cancel-button"
                onClick={() => cancelTimer(timer.id)}
              >
                Cancel
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Ringtone Manager Component
const RingtoneManager = () => {
  const [ringtones, setRingtones] = useState([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchRingtones();
  }, []);

  const fetchRingtones = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/ringtones`);
      setRingtones(response.data.ringtones || []);
    } catch (error) {
      console.error('Error fetching ringtones:', error);
    }
  };

  const uploadRingtone = async (file) => {
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      await axios.post(`${BACKEND_URL}/api/ringtones`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      fetchRingtones();
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('Error uploading ringtone:', error);
      alert('Error uploading ringtone. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const deleteRingtone = async (ringtoneId) => {
    try {
      await axios.delete(`${BACKEND_URL}/api/ringtones/${ringtoneId}`);
      fetchRingtones();
    } catch (error) {
      console.error('Error deleting ringtone:', error);
    }
  };

  const playRingtone = async (ringtoneId) => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/ringtones/${ringtoneId}`);
      const audioData = response.data.file_data;
      const audioBlob = new Blob([Uint8Array.from(atob(audioData), c => c.charCodeAt(0))], 
        { type: response.data.file_type });
      
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audio.play();
      
      setTimeout(() => URL.revokeObjectURL(audioUrl), 1000);
    } catch (error) {
      console.error('Error playing ringtone:', error);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (file.type.startsWith('audio/')) {
        uploadRingtone(file);
      } else {
        alert('Please select an audio file');
      }
    }
  };

  return (
    <div className="ringtone-manager">
      <h3 className="section-title">🎵 Custom Ringtones</h3>
      
      <div className="upload-section">
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*"
          onChange={handleFileSelect}
          className="file-input"
          disabled={uploading}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="upload-button"
          disabled={uploading}
        >
          {uploading ? '⏳ Uploading...' : '📁 Upload Ringtone'}
        </button>
      </div>

      <div className="ringtone-list">
        {ringtones.length === 0 ? (
          <p className="no-ringtones">No custom ringtones uploaded</p>
        ) : (
          ringtones.map((ringtone) => (
            <div key={ringtone.id} className="ringtone-item">
              <div className="ringtone-info">
                <span className="ringtone-name">🎵 {ringtone.name}</span>
                <span className="ringtone-date">
                  {new Date(ringtone.created_at).toLocaleDateString()}
                </span>
              </div>
              <div className="ringtone-actions">
                <button 
                  onClick={() => playRingtone(ringtone.id)}
                  className="play-button"
                >
                  ▶️
                </button>
                <button 
                  onClick={() => deleteRingtone(ringtone.id)}
                  className="delete-button"
                >
                  🗑️
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

// Stopwatch Component
const Stopwatch = () => {
  const [time, setTime] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [laps, setLaps] = useState([]);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (isRunning) {
      intervalRef.current = setInterval(() => {
        setTime(prevTime => prevTime + 10);
      }, 10);
    } else {
      clearInterval(intervalRef.current);
    }

    return () => clearInterval(intervalRef.current);
  }, [isRunning]);

  const formatTime = (time) => {
    const minutes = Math.floor(time / 60000);
    const seconds = Math.floor((time % 60000) / 1000);
    const centiseconds = Math.floor((time % 1000) / 10);
    
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${centiseconds.toString().padStart(2, '0')}`;
  };

  const start = () => setIsRunning(true);
  const stop = () => setIsRunning(false);
  const reset = () => {
    setTime(0);
    setIsRunning(false);
    setLaps([]);
  };

  const addLap = () => {
    if (time > 0) {
      setLaps(prevLaps => [...prevLaps, time]);
    }
  };

  return (
    <div className="stopwatch">
      <h3 className="section-title">⏱️ Stopwatch</h3>
      <div className="stopwatch-display">
        {formatTime(time)}
      </div>
      
      <div className="stopwatch-controls">
        <button 
          onClick={isRunning ? stop : start}
          className={`control-button ${isRunning ? 'stop' : 'start'}`}
        >
          {isRunning ? 'Stop' : 'Start'}
        </button>
        
        <button 
          onClick={addLap}
          className="control-button lap"
          disabled={time === 0}
        >
          Lap
        </button>
        
        <button 
          onClick={reset}
          className="control-button reset"
          disabled={time === 0 && laps.length === 0}
        >
          Reset
        </button>
      </div>

      {laps.length > 0 && (
        <div className="laps-section">
          <h4>Lap Times</h4>
          <div className="laps-list">
            {laps.map((lapTime, index) => (
              <div key={index} className="lap-item">
                <span>Lap {index + 1}</span>
                <span>{formatTime(lapTime)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Main App Component
function App() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleCommandResult = (data) => {
    // Refresh timers when a command is processed
    if (data.type === 'command_processed' || data.type === 'timer_expired' || data.type === 'alarm_triggered') {
      setRefreshTrigger(prev => prev + 1);
    }

    // Show notifications for alarms/timers
    if (data.type === 'timer_expired' || data.type === 'alarm_triggered') {
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(data.message, {
          icon: '/favicon.ico',
          badge: '/favicon.ico'
        });
      }
    }
  };

  // Request notification permission on load
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  return (
    <div className="App">
      {/* Background overlay */}
      <div className="background-overlay"></div>
      
      {/* Main content */}
      <div className="main-container">
        {/* Header with main clock */}
        <header className="app-header">
          <h1 className="app-title">🤖 AI Smart Clock</h1>
          <DigitalClock />
        </header>

        {/* Main content grid */}
        <main className="app-main">
          <div className="left-panel">
            <VoiceCommands onCommandResult={handleCommandResult} />
            <RingtoneManager />
          </div>

          <div className="center-panel">
            <WorldTime />
          </div>

          <div className="right-panel">
            <TimerManager refreshTrigger={refreshTrigger} />
            <Stopwatch />
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;