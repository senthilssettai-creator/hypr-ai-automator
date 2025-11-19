"""
Hyprland Connector - Deep integration with Hyprland compositor
Listens to events, executes dispatchers, queries system state
"""

import asyncio
import json
import os
import socket
import logging
from typing import Dict, List, Optional, Callable
from pathlib import Path


class HyprlandConnector:
    """Manages connection and interaction with Hyprland"""
    
    def __init__(self):
        self.logger = logging.getLogger('hyprland')
        
        # Get Hyprland socket paths
        self.instance_sig = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
        if not self.instance_sig:
            self.logger.warning("HYPRLAND_INSTANCE_SIGNATURE not found, attempting detection...")
            self.instance_sig = self._detect_instance()
        
        self.socket_path = f"/tmp/hypr/{self.instance_sig}/.socket.sock"
        self.socket2_path = f"/tmp/hypr/{self.instance_sig}/.socket2.sock"
        
        self.event_callbacks = []
        self.running = False
        
        self.logger.info(f"Initialized Hyprland connector (instance: {self.instance_sig})")
    
    def _detect_instance(self) -> str:
        """Detect Hyprland instance signature"""
        hypr_dir = Path("/tmp/hypr")
        if hypr_dir.exists():
            instances = [d.name for d in hypr_dir.iterdir() if d.is_dir()]
            if instances:
                return instances[0]
        raise RuntimeError("Could not detect Hyprland instance. Is Hyprland running?")
    
    async def start_event_listener(self):
        """Start listening to Hyprland events on socket2"""
        self.running = True
        self.logger.info("Starting Hyprland event listener...")
        
        while self.running:
            try:
                reader, writer = await asyncio.open_unix_connection(self.socket2_path)
                self.logger.info("Connected to Hyprland event socket")
                
                while self.running:
                    data = await reader.read(4096)
                    if not data:
                        break
                    
                    # Parse events (format: "EVENT>>DATA\n")
                    lines = data.decode('utf-8').strip().split('\n')
                    for line in lines:
                        if '>>' in line:
                            event, event_data = line.split('>>', 1)
                            await self._handle_event(event, event_data)
                
                writer.close()
                await writer.wait_closed()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Event listener error: {e}")
                await asyncio.sleep(5)  # Reconnect delay
    
    async def _handle_event(self, event: str, data: str):
        """Process Hyprland events"""
        event_map = {
            'workspace': 'workspace_changed',
            'focusedmon': 'monitor_changed',
            'activewindow': 'window_focused',
            'openwindow': 'window_opened',
            'closewindow': 'window_closed',
            'movewindow': 'window_moved',
            'activewindowv2': 'window_activated',
            'fullscreen': 'fullscreen_changed',
            'monitoradded': 'monitor_added',
            'monitorremoved': 'monitor_removed',
        }
        
        event_type = event_map.get(event, event)
        self.logger.debug(f"Event: {event_type} -> {data}")
        
        # Notify callbacks
        for callback in self.event_callbacks:
            try:
                await callback(event_type, data)
            except Exception as e:
                self.logger.error(f"Error in event callback: {e}")
    
    def register_event_callback(self, callback: Callable):
        """Register a callback for Hyprland events"""
        self.event_callbacks.append(callback)
    
    async def stop(self):
        """Stop event listener"""
        self.running = False
    
    async def execute_command(self, command: str) -> str:
        """
        Execute a hyprctl command
        
        Args:
            command: Command to execute (e.g., "dispatch workspace 1")
            
        Returns:
            str: Command output
        """
        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            
            # Send command
            writer.write(f"j/{command}".encode())
            await writer.drain()
            
            # Read response
            response = await reader.read(8192)
            
            writer.close()
            await writer.wait_closed()
            
            return response.decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Error executing command '{command}': {e}")
            return json.dumps({"error": str(e)})
    
    async def get_state(self) -> Dict:
        """Get comprehensive Hyprland state"""
        state = {}
        
        try:
            # Get active window
            active_window = await self.execute_command("activewindow")
            state['active_window'] = json.loads(active_window) if active_window else {}
            
            # Get workspace info
            workspaces = await self.execute_command("workspaces")
            state['workspaces'] = json.loads(workspaces) if workspaces else []
            
            # Get monitor info
            monitors = await self.execute_command("monitors")
            state['monitors'] = json.loads(monitors) if monitors else []
            
            # Get all clients (windows)
            clients = await self.execute_command("clients")
            state['clients'] = json.loads(clients) if clients else []
            
            # Get current workspace
            active_workspace = await self.execute_command("activeworkspace")
            state['workspace'] = json.loads(active_workspace) if active_workspace else {}
            
        except Exception as e:
            self.logger.error(f"Error getting Hyprland state: {e}")
        
        return state
    
    async def dispatch(self, dispatcher: str, *args) -> bool:
        """
        Execute a Hyprland dispatcher
        
        Args:
            dispatcher: Dispatcher name (e.g., "exec", "workspace", "movetoworkspace")
            args: Dispatcher arguments
            
        Returns:
            bool: Success status
        """
        try:
            arg_str = ','.join(str(a) for a in args) if args else ''
            command = f"dispatch {dispatcher} {arg_str}".strip()
            
            result = await self.execute_command(command)
            
            # Check for errors in response
            if 'error' in result.lower():
                self.logger.error(f"Dispatcher error: {result}")
                return False
            
            self.logger.info(f"Executed dispatcher: {command}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing dispatcher: {e}")
            return False
    
    async def focus_window(self, identifier: str, by: str = 'class') -> bool:
        """
        Focus a window by class, title, or address
        
        Args:
            identifier: Window identifier
            by: Search method ('class', 'title', 'address')
        """
        if by == 'class':
            return await self.dispatch('focuswindow', f'class:{identifier}')
        elif by == 'title':
            return await self.dispatch('focuswindow', f'title:{identifier}')
        elif by == 'address':
            return await self.dispatch('focuswindow', f'address:{identifier}')
        return False
    
    async def move_window(self, workspace: int) -> bool:
        """Move active window to workspace"""
        return await self.dispatch('movetoworkspace', str(workspace))
    
    async def resize_window(self, width: int, height: int) -> bool:
        """Resize active window"""
        return await self.dispatch('resizeactive', f'{width} {height}')
    
    async def close_window(self, identifier: Optional[str] = None) -> bool:
        """Close a window (active if no identifier)"""
        if identifier:
            await self.focus_window(identifier)
        return await self.dispatch('killactive')
    
    async def exec_app(self, command: str) -> bool:
        """Execute an application"""
        return await self.dispatch('exec', command)
    
    async def switch_workspace(self, workspace: int) -> bool:
        """Switch to workspace"""
        return await self.dispatch('workspace', str(workspace))
    
    async def toggle_fullscreen(self) -> bool:
        """Toggle fullscreen for active window"""
        return await self.dispatch('fullscreen', '1')
    
    async def toggle_floating(self) -> bool:
        """Toggle floating mode for active window"""
        return await self.dispatch('togglefloating')
    
    async def move_cursor(self, x: int, y: int) -> bool:
        """Move cursor to absolute position"""
        return await self.dispatch('movecursor', f'{x} {y}')
    
    async def get_active_window(self) -> Dict:
        """Get information about the active window"""
        try:
            result = await self.execute_command('activewindow')
            return json.loads(result) if result else {}
        except Exception as e:
            self.logger.error(f"Error getting active window: {e}")
            return {}
    
    async def get_all_windows(self) -> List[Dict]:
        """Get all open windows"""
        try:
            result = await self.execute_command('clients')
            return json.loads(result) if result else []
        except Exception as e:
            self.logger.error(f"Error getting windows: {e}")
            return []
    
    async def get_monitors(self) -> List[Dict]:
        """Get all monitors"""
        try:
            result = await self.execute_command('monitors')
            return json.loads(result) if result else []
        except Exception as e:
            self.logger.error(f"Error getting monitors: {e}")
            return []
    
    async def reload_config(self) -> bool:
        """Reload Hyprland configuration"""
        return await self.dispatch('reload')