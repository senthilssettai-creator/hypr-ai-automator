"""
Web Server - FastAPI-based web interface with WebSocket support
Serves dashboard and handles real-time communication
"""

import asyncio
import json
import logging
from typing import Set
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


class WebServer:
    """FastAPI web server for dashboard and API"""
    
    def __init__(self, host: str, port: int, daemon):
        self.logger = logging.getLogger('web_server')
        self.host = host
        self.port = port
        self.daemon = daemon
        
        # Active WebSocket connections
        self.active_connections: Set[WebSocket] = set()
        
        # Create FastAPI app
        self.app = FastAPI(title="Hyprland AI Automator")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
        
        # Static files directory
        self.static_dir = Path(__file__).parent / 'static'
        self.static_dir.mkdir(exist_ok=True)
        
        self.server = None
        self.logger.info(f"Web server initialized on {host}:{port}")
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/")
        async def root():
            """Serve main dashboard"""
            html_path = Path(__file__).parent / 'static' / 'index.html'
            if html_path.exists():
                return FileResponse(html_path)
            return HTMLResponse(self._get_default_html())
        
        @self.app.get("/api/status")
        async def get_status():
            """Get system status"""
            try:
                state = await self.daemon.get_system_state()
                return JSONResponse({
                    'status': 'online',
                    'timestamp': state.get('timestamp'),
                    'system': state.get('system', {}),
                    'hyprland': {
                        'active_window': state.get('hyprland', {}).get('active_window', {}),
                        'workspace': state.get('hyprland', {}).get('workspace', {})
                    }
                })
            except Exception as e:
                return JSONResponse({
                    'status': 'error',
                    'error': str(e)
                }, status_code=500)
        
        @self.app.get("/api/keybindings")
        async def get_keybindings():
            """Get configured keybindings"""
            keybindings = self.daemon.context_manager.get_keybindings()
            return JSONResponse({'keybindings': keybindings})
        
        @self.app.get("/api/history")
        async def get_history():
            """Get command and conversation history"""
            commands = self.daemon.context_manager.get_recent_commands(limit=20)
            conversations = self.daemon.context_manager.get_conversation_history(limit=50)
            return JSONResponse({
                'commands': commands,
                'conversations': conversations
            })
        
        @self.app.get("/api/stats")
        async def get_stats():
            """Get system statistics"""
            stats = self.daemon.context_manager.get_system_stats()
            return JSONResponse(stats)
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time communication"""
            await self._handle_websocket(websocket)
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        
        try:
            self.logger.info(f"WebSocket client connected (total: {len(self.active_connections)})")
            
            # Send welcome message
            await websocket.send_json({
                'type': 'connected',
                'message': 'Connected to AI Automator'
            })
            
            while True:
                # Receive message from client
                data = await websocket.receive_json()
                
                message_type = data.get('type')
                
                if message_type == 'query':
                    # Process AI query
                    query = data.get('query', '')
                    include_screenshot = data.get('screenshot', False)
                    
                    # Send processing status
                    await websocket.send_json({
                        'type': 'processing',
                        'message': 'Processing your request...'
                    })
                    
                    # Process through daemon
                    result = await self.daemon.process_user_query(query, include_screenshot)
                    
                    # Send result
                    await websocket.send_json({
                        'type': 'result',
                        'result': result
                    })
                
                elif message_type == 'ping':
                    await websocket.send_json({'type': 'pong'})
                
                elif message_type == 'get_state':
                    state = await self.daemon.get_system_state()
                    await websocket.send_json({
                        'type': 'state',
                        'state': state
                    })
                
        except WebSocketDisconnect:
            self.logger.info("WebSocket client disconnected")
        except Exception as e:
            self.logger.error(f"WebSocket error: {e}")
        finally:
            self.active_connections.discard(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return
        
        disconnected = set()
        
        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                self.logger.error(f"Error broadcasting to client: {e}")
                disconnected.add(websocket)
        
        # Remove disconnected clients
        self.active_connections -= disconnected
    
    async def start(self):
        """Start the web server"""
        self.logger.info(f"Starting web server on {self.host}:{self.port}")
        
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False
        )
        
        self.server = uvicorn.Server(config)
        await self.server.serve()
    
    async def stop(self):
        """Stop the web server"""
        if self.server:
            self.logger.info("Stopping web server...")
            self.server.should_exit = True
    
    def _get_default_html(self) -> str:
        """Return default HTML if static file not found"""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Hyprland AI Automator</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding: 20px;
                }
                .container {
                    background: white;
                    border-radius: 20px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    max-width: 800px;
                    width: 100%;
                    padding: 40px;
                }
                h1 {
                    color: #667eea;
                    margin-bottom: 10px;
                }
                .subtitle {
                    color: #666;
                    margin-bottom: 30px;
                }
                .status {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    padding: 15px;
                    background: #f0f4ff;
                    border-radius: 10px;
                    margin-bottom: 30px;
                }
                .status-dot {
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    background: #4CAF50;
                    animation: pulse 2s infinite;
                }
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
                .chat-container {
                    border: 2px solid #e0e0e0;
                    border-radius: 15px;
                    height: 400px;
                    display: flex;
                    flex-direction: column;
                }
                .messages {
                    flex: 1;
                    overflow-y: auto;
                    padding: 20px;
                }
                .message {
                    margin-bottom: 15px;
                    padding: 12px 16px;
                    border-radius: 12px;
                    max-width: 80%;
                }
                .message.user {
                    background: #667eea;
                    color: white;
                    margin-left: auto;
                }
                .message.assistant {
                    background: #f0f0f0;
                    color: #333;
                }
                .input-container {
                    display: flex;
                    gap: 10px;
                    padding: 15px;
                    border-top: 2px solid #e0e0e0;
                }
                input {
                    flex: 1;
                    padding: 12px;
                    border: 2px solid #e0e0e0;
                    border-radius: 10px;
                    font-size: 14px;
                }
                input:focus {
                    outline: none;
                    border-color: #667eea;
                }
                button {
                    padding: 12px 24px;
                    background: #667eea;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 600;
                    transition: background 0.3s;
                }
                button:hover {
                    background: #5568d3;
                }
                button:disabled {
                    background: #ccc;
                    cursor: not-allowed;
                }
                .info {
                    margin-top: 20px;
                    padding: 15px;
                    background: #f9f9f9;
                    border-radius: 10px;
                    font-size: 14px;
                    color: #666;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 Hyprland AI Automator</h1>
                <p class="subtitle">AI-powered desktop automation for Arch Linux</p>
                
                <div class="status">
                    <div class="status-dot"></div>
                    <span id="status-text">Connected to daemon</span>
                </div>
                
                <div class="chat-container">
                    <div class="messages" id="messages"></div>
                    <div class="input-container">
                        <input type="text" id="query-input" placeholder="Ask me to do something..." />
                        <button id="send-btn" onclick="sendQuery()">Send</button>
                    </div>
                </div>
                
                <div class="info">
                    <strong>Try commands like:</strong><br>
                    • "Open Firefox and navigate to GitHub"<br>
                    • "Take a screenshot and save it"<br>
                    • "Show me my system resources"<br>
                    • "Switch to workspace 2 and open a terminal"
                </div>
            </div>
            
            <script>
                let ws = null;
                
                function connect() {
                    ws = new WebSocket(`ws://${window.location.host}/ws`);
                    
                    ws.onopen = () => {
                        console.log('Connected to server');
                        document.getElementById('status-text').textContent = 'Connected to daemon';
                    };
                    
                    ws.onmessage = (event) => {
                        const data = JSON.parse(event.data);
                        handleMessage(data);
                    };
                    
                    ws.onerror = (error) => {
                        console.error('WebSocket error:', error);
                        document.getElementById('status-text').textContent = 'Connection error';
                    };
                    
                    ws.onclose = () => {
                        console.log('Disconnected from server');
                        document.getElementById('status-text').textContent = 'Disconnected';
                        setTimeout(connect, 3000);
                    };
                }
                
                function handleMessage(data) {
                    const messagesDiv = document.getElementById('messages');
                    
                    if (data.type === 'result') {
                        const result = data.result;
                        addMessage('assistant', result.explanation || 'Done!');
                        
                        if (result.actions && result.actions.length > 0) {
                            const actionsSummary = result.actions.map(a => 
                                `${a.success ? '✓' : '✗'} ${JSON.stringify(a.action).substring(0, 50)}...`
                            ).join('<br>');
                            addMessage('assistant', actionsSummary, true);
                        }
                    } else if (data.type === 'processing') {
                        addMessage('assistant', data.message);
                    }
                }
                
                function addMessage(role, content, isHtml = false) {
                    const messagesDiv = document.getElementById('messages');
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message ${role}`;
                    
                    if (isHtml) {
                        messageDiv.innerHTML = content;
                    } else {
                        messageDiv.textContent = content;
                    }
                    
                    messagesDiv.appendChild(messageDiv);
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                }
                
                function sendQuery() {
                    const input = document.getElementById('query-input');
                    const query = input.value.trim();
                    
                    if (!query || !ws || ws.readyState !== WebSocket.OPEN) return;
                    
                    addMessage('user', query);
                    
                    ws.send(JSON.stringify({
                        type: 'query',
                        query: query,
                        screenshot: false
                    }));
                    
                    input.value = '';
                }
                
                document.getElementById('query-input').addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') sendQuery();
                });
                
                connect();
            </script>
        </body>
        </html>
        """