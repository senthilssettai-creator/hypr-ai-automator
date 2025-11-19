#!/usr/bin/env python3
"""
Hyprland AI Automator - Main Daemon
Orchestrates all components and manages system state
"""

import asyncio
import signal
import sys
import os
import logging
from pathlib import Path
from datetime import datetime
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.system_monitor import SystemMonitor
from core.hyprland_connector import HyprlandConnector
from core.action_dispatcher import ActionDispatcher
from core.context_manager import ContextManager
from web.server import WebServer
from ai.gemini_client import GeminiClient
from utils.config import Config
from utils.logger import setup_logger

class AIAutomatorDaemon:
    """Main daemon orchestrating all subsystems"""
    
    def __init__(self):
        self.config = Config()
        self.logger = setup_logger('daemon', self.config.log_level)
        
        # Initialize subsystems
        self.context_manager = ContextManager(self.config.db_path)
        self.hyprland = HyprlandConnector()
        self.system_monitor = SystemMonitor()
        self.action_dispatcher = ActionDispatcher(self.hyprland, self.system_monitor)
        self.gemini_client = GeminiClient(
            api_key=self.config.gemini_api_key,
            model=self.config.gemini_model
        )
        self.web_server = WebServer(
            host=self.config.host,
            port=self.config.port,
            daemon=self
        )
        
        self.running = False
        self.tasks = []
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("AI Automator Daemon initialized")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False
    
    async def start(self):
        """Start all daemon subsystems"""
        self.running = True
        self.logger.info("Starting AI Automator Daemon...")
        
        try:
            # Start subsystems
            self.tasks = [
                asyncio.create_task(self.hyprland.start_event_listener(), name="hyprland_events"),
                asyncio.create_task(self.system_monitor.start_monitoring(), name="system_monitor"),
                asyncio.create_task(self.web_server.start(), name="web_server"),
                asyncio.create_task(self._periodic_context_update(), name="context_updater"),
            ]
            
            self.logger.info(f"All subsystems started. Dashboard: http://{self.config.host}:{self.config.port}")
            
            # Wait for all tasks
            await asyncio.gather(*self.tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"Fatal error in daemon: {e}", exc_info=True)
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop all subsystems gracefully"""
        self.logger.info("Stopping AI Automator Daemon...")
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Stop subsystems
        await self.web_server.stop()
        await self.hyprland.stop()
        self.context_manager.close()
        
        self.logger.info("Daemon stopped successfully")
    
    async def _periodic_context_update(self):
        """Periodically update system context in database"""
        while self.running:
            try:
                # Gather current system state
                state = await self.get_system_state()
                
                # Update context database
                self.context_manager.update_system_state(state)
                
                # Sleep for 30 seconds
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in context updater: {e}")
                await asyncio.sleep(30)
    
    async def get_system_state(self):
        """Gather complete system state for AI context"""
        state = {
            'timestamp': datetime.now().isoformat(),
            'hyprland': await self.hyprland.get_state(),
            'system': await self.system_monitor.get_state(),
            'keybindings': self.context_manager.get_keybindings(),
            'recent_commands': self.context_manager.get_recent_commands(limit=10),
        }
        return state
    
    async def process_user_query(self, query: str, include_screenshot: bool = False):
        """
        Process a user query through the AI pipeline
        
        Args:
            query: User's natural language command
            include_screenshot: Whether to include a screenshot in context
            
        Returns:
            dict: Response with actions and explanations
        """
        try:
            self.logger.info(f"Processing query: {query[:100]}...")
            
            # Get current system state
            system_state = await self.get_system_state()
            
            # Get screenshot if requested
            screenshot_data = None
            if include_screenshot:
                screenshot_data = await self.action_dispatcher.take_screenshot()
            
            # Build context for Gemini
            context = self._build_ai_context(system_state, screenshot_data)
            
            # Send to Gemini
            response = await self.gemini_client.process_query(query, context)
            
            # Parse and execute actions
            result = await self._execute_ai_response(response)
            
            # Store in conversation history
            self.context_manager.add_conversation(query, 'user')
            self.context_manager.add_conversation(json.dumps(result), 'assistant')
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing query: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'actions': []
            }
    
    def _build_ai_context(self, system_state: dict, screenshot_data: bytes = None):
        """Build comprehensive context for AI"""
        context = {
            'system_info': {
                'os': 'Arch Linux',
                'compositor': 'Hyprland',
                'active_window': system_state['hyprland'].get('active_window'),
                'workspace': system_state['hyprland'].get('workspace'),
                'monitors': system_state['hyprland'].get('monitors'),
            },
            'available_actions': self.action_dispatcher.get_available_actions(),
            'keybindings': system_state.get('keybindings', []),
            'recent_activity': system_state.get('recent_commands', []),
            'system_resources': system_state['system'],
        }
        
        if screenshot_data:
            import base64
            context['screenshot'] = base64.b64encode(screenshot_data).decode('utf-8')
        
        return context
    
    async def _execute_ai_response(self, response: dict):
        """Execute actions from AI response"""
        results = []
        
        actions = response.get('actions', [])
        explanation = response.get('explanation', '')
        
        self.logger.info(f"Executing {len(actions)} actions: {explanation}")
        
        for action in actions:
            try:
                result = await self.action_dispatcher.execute(action)
                results.append({
                    'action': action,
                    'success': result['success'],
                    'output': result.get('output', '')
                })
                
                # Log to history
                self.context_manager.add_command(
                    command=str(action),
                    output=result.get('output', ''),
                    success=result['success']
                )
                
                # Small delay between actions
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error executing action {action}: {e}")
                results.append({
                    'action': action,
                    'success': False,
                    'error': str(e)
                })
        
        return {
            'success': all(r['success'] for r in results),
            'explanation': explanation,
            'actions': results,
            'timestamp': datetime.now().isoformat()
        }


async def main():
    """Main entry point"""
    daemon = AIAutomatorDaemon()
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        daemon.logger.info("Received keyboard interrupt")
    except Exception as e:
        daemon.logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    # Set event loop policy for compatibility
    if sys.platform == 'linux':
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    
    asyncio.run(main())