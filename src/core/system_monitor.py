"""
System Monitor - Tracks system resources and status
CPU, memory, disk, network, battery, audio, etc.
"""

import asyncio
import logging
import psutil
import subprocess
from typing import Dict, Optional
from datetime import datetime


class SystemMonitor:
    """Monitor system resources and status"""
    
    def __init__(self):
        self.logger = logging.getLogger('system_monitor')
        self.running = False
        self.current_state = {}
        self.update_interval = 5  # seconds
        
        self.logger.info("System monitor initialized")
    
    async def start_monitoring(self):
        """Start continuous system monitoring"""
        self.running = True
        self.logger.info("Starting system monitoring...")
        
        while self.running:
            try:
                self.current_state = await self._gather_system_state()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in system monitor: {e}")
                await asyncio.sleep(self.update_interval)
    
    async def get_state(self) -> Dict:
        """Get current system state"""
        if not self.current_state:
            self.current_state = await self._gather_system_state()
        return self.current_state
    
    async def _gather_system_state(self) -> Dict:
        """Gather comprehensive system information"""
        state = {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'cpu_count': psutil.cpu_count(),
            'memory_percent': psutil.virtual_memory().percent,
            'memory_available_gb': round(psutil.virtual_memory().available / (1024**3), 2),
            'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'disk_usage': self._get_disk_usage(),
            'network': await self._get_network_info(),
            'battery': self._get_battery_info(),
            'audio': await self._get_audio_info(),
            'bluetooth': await self._get_bluetooth_info(),
            'load_average': psutil.getloadavg(),
            'uptime_seconds': self._get_uptime(),
        }
        
        return state
    
    def _get_disk_usage(self) -> Dict:
        """Get disk usage for root partition"""
        try:
            usage = psutil.disk_usage('/')
            return {
                'total_gb': round(usage.total / (1024**3), 2),
                'used_gb': round(usage.used / (1024**3), 2),
                'free_gb': round(usage.free / (1024**3), 2),
                'percent': usage.percent
            }
        except Exception as e:
            self.logger.error(f"Error getting disk usage: {e}")
            return {}
    
    async def _get_network_info(self) -> Dict:
        """Get network connection status"""
        try:
            # Check WiFi status
            proc = await asyncio.create_subprocess_exec(
                'nmcli', '-t', '-f', 'ACTIVE,SSID', 'dev', 'wifi',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            wifi_connected = False
            wifi_ssid = None
            
            if proc.returncode == 0:
                lines = stdout.decode().strip().split('\n')
                for line in lines:
                    if line.startswith('yes:'):
                        wifi_connected = True
                        wifi_ssid = line.split(':', 1)[1] if ':' in line else None
                        break
            
            # Get network stats
            net_io = psutil.net_io_counters()
            
            return {
                'wifi_connected': wifi_connected,
                'wifi_ssid': wifi_ssid,
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
            }
        except Exception as e:
            self.logger.error(f"Error getting network info: {e}")
            return {'wifi_connected': False}
    
    def _get_battery_info(self) -> Optional[Dict]:
        """Get battery information (if laptop)"""
        try:
            battery = psutil.sensors_battery()
            if battery:
                return {
                    'percent': battery.percent,
                    'plugged': battery.power_plugged,
                    'time_left_minutes': battery.secsleft // 60 if battery.secsleft > 0 else None
                }
            return None
        except Exception as e:
            self.logger.debug(f"No battery detected: {e}")
            return None
    
    async def _get_audio_info(self) -> Dict:
        """Get audio volume and mute status"""
        try:
            # Get volume using pactl
            proc = await asyncio.create_subprocess_exec(
                'pactl', 'get-sink-volume', '@DEFAULT_SINK@',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            volume = 0
            if proc.returncode == 0:
                # Parse volume (format: "Volume: front-left: 65536 / 100% / 0.00 dB")
                output = stdout.decode()
                if '%' in output:
                    volume_str = output.split('%')[0].split()[-1]
                    volume = int(volume_str)
            
            # Get mute status
            proc = await asyncio.create_subprocess_exec(
                'pactl', 'get-sink-mute', '@DEFAULT_SINK@',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            muted = 'yes' in stdout.decode().lower()
            
            return {
                'volume': volume,
                'muted': muted
            }
        except Exception as e:
            self.logger.error(f"Error getting audio info: {e}")
            return {'volume': 0, 'muted': False}
    
    async def _get_bluetooth_info(self) -> Dict:
        """Get Bluetooth status"""
        try:
            proc = await asyncio.create_subprocess_exec(
                'bluetoothctl', 'show',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            output = stdout.decode()
            powered = 'Powered: yes' in output
            
            return {
                'powered': powered,
                'available': proc.returncode == 0
            }
        except Exception as e:
            self.logger.debug(f"Bluetooth not available: {e}")
            return {'powered': False, 'available': False}
    
    def _get_uptime(self) -> int:
        """Get system uptime in seconds"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                return int(uptime_seconds)
        except Exception:
            return 0
    
    async def get_running_processes(self, limit: int = 20) -> list:
        """Get list of running processes sorted by CPU usage"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    info = proc.info
                    processes.append({
                        'pid': info['pid'],
                        'name': info['name'],
                        'cpu_percent': info['cpu_percent'],
                        'memory_percent': info['memory_percent']
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Sort by CPU usage
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            return processes[:limit]
        except Exception as e:
            self.logger.error(f"Error getting processes: {e}")
            return []
    
    async def get_temperature(self) -> Optional[Dict]:
        """Get system temperature sensors"""
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                result = {}
                for name, entries in temps.items():
                    result[name] = [
                        {
                            'label': entry.label,
                            'current': entry.current,
                            'high': entry.high,
                            'critical': entry.critical
                        }
                        for entry in entries
                    ]
                return result
            return None
        except Exception as e:
            self.logger.debug(f"Temperature sensors not available: {e}")
            return None
            