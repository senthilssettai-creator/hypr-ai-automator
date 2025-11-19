"""
Gemini Client - Interface to Google's Gemini AI API
Uses the latest google-genai SDK
"""

import json
import logging
from typing import Dict, List, Optional
from google import genai
from google.genai import types


class GeminiClient:
    """Client for interacting with Gemini API"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.logger = logging.getLogger('gemini')
        self.api_key = api_key
        self.model = model
        
        # Initialize client
        self.client = genai.Client(api_key=api_key)
        
        # System prompt for desktop automation
        self.system_prompt = self._build_system_prompt()
        
        self.logger.info(f"Initialized Gemini client with model: {model}")
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt"""
        return """You are an advanced AI assistant with complete control over an Arch Linux system running Hyprland (Wayland compositor). You have the ability to:

1. **Control Applications**: Launch, focus, move, resize, and close any application
2. **Manage Windows**: Switch workspaces, tile windows, toggle fullscreen/floating
3. **Input Simulation**: Type text, press key combinations, move and click the mouse
4. **Execute Commands**: Run any shell command, script, or function
5. **System Control**: Manage audio, brightness, Bluetooth, WiFi, processes
6. **File Operations**: Read, write, and modify files
7. **Visual Context**: Analyze screenshots when provided

**Response Format**: Always respond in JSON format with this structure:
```json
{
  "explanation": "Brief explanation of what you're doing and why",
  "actions": [
    {
      "type": "action_type",
      "params": {...}
    }
  ]
}
```

**Available Action Types**:

1. `keyboard` - Simulate keyboard input
   - params: {"keys": "string or key combo", "delay": 0.05}
   - Examples: {"keys": "hello"}, {"keys": "Super+Return"}

2. `mouse_move` - Move mouse cursor
   - params: {"x": 100, "y": 200, "relative": false}

3. `mouse_click` - Click mouse button
   - params: {"button": "left|right|middle", "clicks": 1}

4. `execute` - Run shell command
   - params: {"command": "ls -la", "wait": true, "terminal": false}

5. `hyprland_dispatch` - Execute Hyprland dispatcher
   - params: {"dispatcher": "exec", "args": ["firefox"]}
   - Common dispatchers: exec, workspace, movetoworkspace, togglefloating, fullscreen

6. `focus_window` - Focus specific window
   - params: {"identifier": "firefox", "by": "class|title|address"}

7. `screenshot` - Take screenshot
   - params: {"region": "full|selection|window", "save": true}

8. `file_write` - Write to file
   - params: {"path": "/path/to/file", "content": "text"}

9. `file_read` - Read from file
   - params: {"path": "/path/to/file"}

10. `audio_control` - Control system audio
    - params: {"action": "volume_up|volume_down|mute|unmute", "value": 10}

11. `brightness` - Control screen brightness
    - params: {"action": "set|increase|decrease", "value": 10}

12. `process_control` - Manage processes
    - params: {"action": "kill|list", "identifier": "process_name"}

**Important Guidelines**:
- Break complex tasks into multiple actions
- Use delays between rapid actions
- Always explain your reasoning
- Check context for available keybindings before creating new ones
- Use existing user configurations when possible
- Be conservative with destructive actions (killing processes, deleting files)
- Ask for confirmation for potentially dangerous operations

**User Context**: You will receive comprehensive system context including:
- Current active window and workspace
- Available keybindings from user's config
- Recent command history
- System resource usage
- Screenshot data (when provided)

Use this context to make intelligent decisions about how to fulfill the user's request."""

    async def process_query(self, query: str, context: Dict) -> Dict:
        """
        Process user query with full system context
        
        Args:
            query: User's natural language command
            context: System context (state, keybindings, etc.)
            
        Returns:
            dict: Parsed response with actions
        """
        try:
            # Build the full prompt
            full_prompt = self._build_prompt(query, context)
            
            # Configure generation
            config = types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=4096,
                response_mime_type="application/json"
            )
            
            # Handle screenshot if present
            contents = []
            if context.get('screenshot'):
                import base64
                screenshot_bytes = base64.b64decode(context['screenshot'])
                contents.append({
                    'mime_type': 'image/png',
                    'data': screenshot_bytes
                })
            
            contents.append(full_prompt)
            
            # Generate response
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config
            )
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            parsed_response = json.loads(response_text.strip())
            
            self.logger.info(f"Gemini response: {parsed_response.get('explanation', '')}")
            
            return parsed_response
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Gemini response: {e}")
            return {
                'explanation': 'Error: Could not parse AI response',
                'actions': [],
                'error': str(e)
            }
        except Exception as e:
            self.logger.error(f"Error processing query: {e}", exc_info=True)
            return {
                'explanation': f'Error communicating with AI: {str(e)}',
                'actions': [],
                'error': str(e)
            }
    
    def _build_prompt(self, query: str, context: Dict) -> str:
        """Build comprehensive prompt with context"""
        
        # Extract key context elements
        active_window = context.get('system_info', {}).get('active_window', {})
        workspace = context.get('system_info', {}).get('workspace', {})
        keybindings = context.get('keybindings', [])[:20]  # Limit to 20 most relevant
        recent_commands = context.get('recent_activity', [])[:5]
        
        prompt = f"""{self.system_prompt}

**Current System State**:
- Active Window: {active_window.get('class', 'None')} - {active_window.get('title', '')}
- Workspace: {workspace.get('id', 'Unknown')}
- Monitors: {len(context.get('system_info', {}).get('monitors', []))}

**User's Configured Keybindings** (sample):
{self._format_keybindings(keybindings)}

**Recent Commands** (for context):
{self._format_recent_commands(recent_commands)}

**System Resources**:
- CPU: {context.get('system_resources', {}).get('cpu_percent', 0):.1f}%
- Memory: {context.get('system_resources', {}).get('memory_percent', 0):.1f}%
- Battery: {context.get('system_resources', {}).get('battery', 'N/A')}

**User Query**: {query}

**Your Response** (must be valid JSON):"""

        return prompt
    
    def _format_keybindings(self, keybindings: List[Dict]) -> str:
        """Format keybindings for context"""
        if not keybindings:
            return "No keybindings loaded yet"
        
        lines = []
        for kb in keybindings[:15]:  # Limit display
            mod = kb.get('modifiers', '')
            key = kb.get('key', '')
            action = kb.get('action', '')
            lines.append(f"  - {mod}+{key}: {action}")
        
        return '\n'.join(lines) if lines else "None configured"
    
    def _format_recent_commands(self, commands: List[Dict]) -> str:
        """Format recent commands for context"""
        if not commands:
            return "No recent commands"
        
        lines = []
        for cmd in commands[:5]:
            command = cmd.get('command', '')
            success = '✓' if cmd.get('success') else '✗'
            lines.append(f"  {success} {command[:60]}")
        
        return '\n'.join(lines) if lines else "None"
    
    async def chat(self, messages: List[Dict]) -> str:
        """
        Simple chat interface without action parsing
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            str: AI response text
        """
        try:
            # Create chat session
            chat = self.client.chats.create(model=self.model)
            
            # Send messages
            for msg in messages:
                if msg['role'] == 'user':
                    response = chat.send_message(msg['content'])
            
            return response.text
            
        except Exception as e:
            self.logger.error(f"Chat error: {e}")
            return f"Error: {str(e)}"