"""
Action Dispatcher - Executes actions from AI responses
Handles keyboard, mouse, shell commands, and system control
"""

import asyncio
import subprocess
import logging
import os
from typing import Dict, Any, List
from pathlib import Path


class ActionDispatcher:
    """Executes actions safely and reports results"""
    
    def __init__(self, hyprland_connector, system_monitor):
        self.logger = logging.getLogger('dispatcher')
        self.hyprland = hyprland_connector
        self.system_monitor = system_monitor
        
        # Action handlers mapping
        self.handlers = {
            'keyboard': self._handle_keyboard,
            'mouse_move': self._handle_mouse_move,
            'mouse_click': self._handle_mouse_click,
            'execute': self._handle_execute,
            'hyprland_dispatch': self._handle_hyprland_dispatch,
            'focus_window': self._handle_focus_window,
            'screenshot': self._handle_screenshot,
            'file_write': self._handle_file_write,
            'file_read': self._handle_file_read,
            'audio_control': self._handle_audio_control,
            'brightness': self._handle_brightness,
            'process_control': self._handle_process_control,
        }
        
        self.logger.info("Action dispatcher initialized")
    
    async def execute(self, action: Dict[str, Any]) -> Dict:
        """
        Execute a single action
        
        Args:
            action: Action dict with 'type' and 'params'
            
        Returns:
            dict: Result with success status and output
        """
        action_type = action.get('type')
        params = action.get('params', {})
        
        if action_type not in self.handlers:
            return {
                'success': False,
                'error': f'Unknown action type: {action_type}'
            }
        
        try:
            self.logger.info(f"Executing action: {action_type} with params: {params}")
            result = await self.handlers[action_type](params)
            return {
                'success': True,
                'output': result
            }
        except Exception as e:
            self.logger.error(f"Error executing {action_type}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_available_actions(self) -> List[str]:
        """Get list of available action types"""
        return list(self.handlers.keys())
    
    # ==================== Action Handlers ====================
    
    async def _handle_keyboard(self, params: Dict) -> str:
        """Simulate keyboard input using ydotool"""
        keys = params.get('keys', '')
        delay = params.get('delay', 0.05)
        
        if not keys:
            raise ValueError("No keys specified")
        
        # Parse key combinations (e.g., "Super+Return", "Ctrl+Alt+T")
        if '+' in keys and len(keys.split('+')) <= 4:
            # It's a key combination
            return await self._send_key_combo(keys)
        else:
            # It's text to type
            return await self._type_text(keys, delay)
    
    async def _send_key_combo(self, combo: str) -> str:
        """Send a key combination"""
        # Map modifier names to ydotool key codes
        modifier_map = {
            'super': '125',  # Left Super
            'ctrl': '29',    # Left Ctrl
            'alt': '56',     # Left Alt
            'shift': '42',   # Left Shift
        }
        
        key_map = {
            'return': '28',
            'enter': '28',
            'space': '57',
            'tab': '15',
            'esc': '1',
            'escape': '1',
            'backspace': '14',
            'delete': '111',
            'left': '105',
            'right': '106',
            'up': '103',
            'down': '108',
            'home': '102',
            'end': '107',
            'pageup': '104',
            'pagedown': '109',
        }
        
        # Parse combo
        parts = [p.strip().lower() for p in combo.split('+')]
        
        # Build ydotool command
        key_presses = []
        key_releases = []
        
        for part in parts:
            if part in modifier_map:
                key_code = modifier_map[part]
            elif part in key_map:
                key_code = key_map[part]
            elif len(part) == 1 and part.isalpha():
                # Letter key - approximate mapping
                key_code = str(ord(part.lower()) - ord('a') + 30)
            else:
                self.logger.warning(f"Unknown key: {part}, skipping")
                continue
            
            key_presses.append(f"{key_code}:1")
            key_releases.insert(0, f"{key_code}:0")  # Release in reverse order
        
        # Combine press and release
        all_keys = key_presses + key_releases
        
        cmd = ['ydotool', 'key'] + all_keys
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"ydotool error: {stderr.decode()}")
        
        return f"Sent key combo: {combo}"
    
    async def _type_text(self, text: str, delay: float) -> str:
        """Type text using ydotool"""
        cmd = ['ydotool', 'type', '--key-delay', str(int(delay * 1000)), text]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"ydotool error: {stderr.decode()}")
        
        return f"Typed: {text[:50]}..."
    
    async def _handle_mouse_move(self, params: Dict) -> str:
        """Move mouse cursor"""
        x = params.get('x', 0)
        y = params.get('y', 0)
        relative = params.get('relative', False)
        
        if relative:
            cmd = ['ydotool', 'mousemove', '--', str(x), str(y)]
        else:
            cmd = ['ydotool', 'mousemove', '-a', str(x), str(y)]
        
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        
        return f"Moved mouse to ({x}, {y})"
    
    async def _handle_mouse_click(self, params: Dict) -> str:
        """Click mouse button"""
        button_map = {
            'left': '0xC0',
            'right': '0xC1',
            'middle': '0xC2',
        }
        
        button = params.get('button', 'left')
        clicks = params.get('clicks', 1)
        
        button_code = button_map.get(button, '0xC0')
        
        cmd = ['ydotool', 'click'] + [button_code] * clicks
        
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        
        return f"Clicked {button} button {clicks} time(s)"
    
    async def _handle_execute(self, params: Dict) -> str:
        """Execute shell command"""
        command = params.get('command', '')
        wait = params.get('wait', True)
        terminal = params.get('terminal', False)
        
        if not command:
            raise ValueError("No command specified")
        
        # Security check - don't allow certain dangerous commands
        dangerous_patterns = ['rm -rf /', 'mkfs', 'dd if=']
        if any(pattern in command for pattern in dangerous_patterns):
            raise RuntimeError("Dangerous command blocked for safety")
        
        if terminal:
            # Execute in terminal emulator
            term = await self._detect_terminal()
            command = f"{term} -e {command}"
        
        if wait:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            output = stdout.decode()[:1000]  # Limit output
            if stderr:
                output += f"\nErrors: {stderr.decode()[:500]}"
            
            return output or "Command executed successfully"
        else:
            # Fire and forget
            subprocess.Popen(command, shell=True, start_new_session=True)
            return "Command launched in background"
    
    async def _detect_terminal(self) -> str:
        """Detect which terminal emulator is installed"""
        terminals = ['kitty', 'alacritty', 'foot', 'wezterm', 'terminator', 'gnome-terminal']
        for term in terminals:
            if subprocess.run(['which', term], capture_output=True).returncode == 0:
                return term
        return 'xterm'  # Fallback
    
    async def _handle_hyprland_dispatch(self, params: Dict) -> str:
        """Execute Hyprland dispatcher"""
        dispatcher = params.get('dispatcher', '')
        args = params.get('args', [])
        
        if not dispatcher:
            raise ValueError("No dispatcher specified")
        
        success = await self.hyprland.dispatch(dispatcher, *args)
        
        if not success:
            raise RuntimeError(f"Dispatcher failed: {dispatcher}")
        
        return f"Executed: {dispatcher} {' '.join(str(a) for a in args)}"
    
    async def _handle_focus_window(self, params: Dict) -> str:
        """Focus a specific window"""
        identifier = params.get('identifier', '')
        by = params.get('by', 'class')
        
        success = await self.hyprland.focus_window(identifier, by)
        
        if not success:
            raise RuntimeError(f"Could not focus window: {identifier}")
        
        return f"Focused window: {identifier}"
    
    async def take_screenshot(self, region: str = 'full') -> bytes:
        """Take screenshot and return bytes"""
        if region == 'full':
            cmd = ['grim', '-']
        elif region == 'selection':
            cmd = ['grim', '-g', '$(slurp)', '-']
        else:
            cmd = ['grim', '-']
        
        proc = await asyncio.create_subprocess_shell(
            ' '.join(cmd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"Screenshot failed: {stderr.decode()}")
        
        return stdout
    
    async def _handle_screenshot(self, params: Dict) -> str:
        """Handle screenshot action"""
        region = params.get('region', 'full')
        save = params.get('save', False)
        
        screenshot_data = await self.take_screenshot(region)
        
        if save:
            # Save to ~/Pictures/screenshots/
            screenshot_dir = Path.home() / 'Pictures' / 'screenshots'
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            
            from datetime import datetime
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = screenshot_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(screenshot_data)
            
            return f"Screenshot saved: {filepath}"
        
        return f"Screenshot captured ({len(screenshot_data)} bytes)"
    
    async def _handle_file_write(self, params: Dict) -> str:
        """Write to file"""
        path = params.get('path', '')
        content = params.get('content', '')
        
        if not path:
            raise ValueError("No path specified")
        
        filepath = Path(path).expanduser()
        
        # Security: only allow writing to home directory
        if not str(filepath).startswith(str(Path.home())):
            raise RuntimeError("Can only write to files in home directory")
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        return f"Wrote {len(content)} bytes to {filepath}"
    
    async def _handle_file_read(self, params: Dict) -> str:
        """Read from file"""
        path = params.get('path', '')
        
        if not path:
            raise ValueError("No path specified")
        
        filepath = Path(path).expanduser()
        
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Limit file size
        if filepath.stat().st_size > 1024 * 1024:  # 1MB
            raise RuntimeError("File too large (max 1MB)")
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        return content[:5000]  # Limit to 5000 chars
    
    async def _handle_audio_control(self, params: Dict) -> str:
        """Control system audio"""
        action = params.get('action', '')
        value = params.get('value', 10)
        
        if action == 'volume_up':
            cmd = ['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'+{value}%']
        elif action == 'volume_down':
            cmd = ['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'-{value}%']
        elif action == 'mute':
            cmd = ['pactl', 'set-sink-mute', '@DEFAULT_SINK@', 'toggle']
        else:
            raise ValueError(f"Unknown audio action: {action}")
        
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        
        return f"Audio: {action}"
    
    async def _handle_brightness(self, params: Dict) -> str:
        """Control screen brightness"""
        action = params.get('action', 'set')
        value = params.get('value', 10)
        
        if action == 'set':
            cmd = ['brightnessctl', 'set', f'{value}%']
        elif action == 'increase':
            cmd = ['brightnessctl', 'set', f'+{value}%']
        elif action == 'decrease':
            cmd = ['brightnessctl', 'set', f'{value}%-']
        else:
            raise ValueError(f"Unknown brightness action: {action}")
        
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        
        return f"Brightness: {action} {value}"
    
    async def _handle_process_control(self, params: Dict) -> str:
        """Manage system processes"""
        action = params.get('action', '')
        identifier = params.get('identifier', '')
        
        if action == 'list':
            cmd = ['ps', 'aux']
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            return stdout.decode()[:2000]
        
        elif action == 'kill':
            if not identifier:
                raise ValueError("No process identifier specified")
            
            cmd = ['pkill', identifier]
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.communicate()
            
            return f"Killed process: {identifier}"
        
        else:
            raise ValueError(f"Unknown process action: {action}")