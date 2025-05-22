import asyncio
import json
import logging
import os
import subprocess
import sys
from typing import Optional, List, Dict

import pycountry
import requests

from models.vpn import VPNRegion, VPNService, VPNServicePool, VPNProvider, VPNStatus
from config import config, DATA_DIR

class VPNManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.vpn_pool = VPNServicePool()
        self.current_service: Optional[VPNService] = None
        self.vpn_file = os.path.join(DATA_DIR, "vpn_services.json")
        self.lock = asyncio.Lock()
        self.connection_process = None
    
    async def initialize(self):
        
        await self.load_vpn_services()
        
        
        if not self.vpn_pool.services:
            await self.add_default_services()
        
        self.logger.info(f"Initialized VPNManager with {len(self.vpn_pool.services)} services")
    
    async def add_service(self, provider: VPNProvider, name: str, auth_data: Dict = None) -> VPNService:
        
        async with self.lock:
            
            existing_service = self.vpn_pool.get_service_by_name(name)
            if existing_service:
                self.logger.warning(f"VPN service with name {name} already exists")
                return existing_service
            
            
            service = VPNService(
                provider=provider,
                name=name,
                auth_data=auth_data or {},
                status=VPNStatus.DISCONNECTED
            )
            
            
            if provider == VPNProvider.NORDVPN or provider == VPNProvider.SURFSHARK:
                await self._add_standard_regions(service)
            
            self.vpn_pool.add_service(service)
            self.logger.info(f"Added new VPN service: {name} ({provider})")
            
            
            await self.save_vpn_services()
            
            return service
    
    async def remove_service(self, provider: VPNProvider, name: str) -> bool:
        
        async with self.lock:
            initial_count = len(self.vpn_pool.services)
            self.vpn_pool.remove_service(provider, name)
            
            if len(self.vpn_pool.services) < initial_count:
                self.logger.info(f"Removed VPN service: {name} ({provider})")
                await self.save_vpn_services()
                return True
            else:
                self.logger.warning(f"VPN service {name} ({provider}) not found")
                return False
    
    async def get_service(self, name: str) -> Optional[VPNService]:
        
        return self.vpn_pool.get_service_by_name(name)
    
    async def add_region(self, service_name: str, region_id: str, region_name: str, region_code: str) -> Optional[VPNRegion]:
        
        async with self.lock:
            service = await self.get_service(service_name)
            if not service:
                self.logger.error(f"VPN service {service_name} not found")
                return None
            
            
            existing_region = service.get_region_by_id(region_id)
            if existing_region:
                self.logger.warning(f"Region with ID {region_id} already exists for service {service_name}")
                return existing_region
            
            
            region = VPNRegion(
                id=region_id,
                name=region_name,
                code=region_code,
                is_active=True
            )
            
            service.add_region(region)
            self.logger.info(f"Added new region {region_name} ({region_code}) to service {service_name}")
            
            
            await self.save_vpn_services()
            
            return region
    
    async def remove_region(self, service_name: str, region_id: str) -> bool:
        
        async with self.lock:
            service = await self.get_service(service_name)
            if not service:
                self.logger.error(f"VPN service {service_name} not found")
                return False
            
            
            existing_region = service.get_region_by_id(region_id)
            if not existing_region:
                self.logger.warning(f"Region with ID {region_id} not found for service {service_name}")
                return False
            
            service.remove_region(region_id)
            self.logger.info(f"Removed region with ID {region_id} from service {service_name}")
            
            
            await self.save_vpn_services()
            
            return True
    
    async def connect(self, service_name: str, region_code: str) -> bool:
        
        async with self.lock:
            
            if self.current_service and self.current_service.status == VPNStatus.CONNECTED:
                await self.disconnect()
            
            service = await self.get_service(service_name)
            if not service:
                self.logger.error(f"VPN service {service_name} not found")
                return False
            
            
            region = service.get_region_by_code(region_code)
            if not region:
                self.logger.error(f"Region with code {region_code} not found for service {service_name}")
                return False
            
            
            if not region.is_active:
                self.logger.error(f"Region {region.name} is not active for service {service_name}")
                return False
            
            
            service.set_current_region(region)
            service.set_connecting()
            
            
            try:
                if service.provider == VPNProvider.NORDVPN:
                    success = await self._connect_nordvpn(service, region)
                elif service.provider == VPNProvider.SURFSHARK:
                    success = await self._connect_surfshark(service, region)
                elif service.provider == VPNProvider.CUSTOM:
                    success = await self._connect_custom(service, region)
                else:
                    self.logger.error(f"Unsupported VPN provider: {service.provider}")
                    service.set_error(f"Unsupported VPN provider: {service.provider}")
                    return False
                
                if success:
                    service.set_connected()
                    self.current_service = service
                    self.logger.info(f"Connected to {service_name} ({region.name})")
                    return True
                else:
                    service.set_error("Failed to connect to VPN")
                    self.logger.error(f"Failed to connect to {service_name} ({region.name})")
                    return False
            
            except Exception as e:
                error_msg = f"Error connecting to VPN: {str(e)}"
                self.logger.error(error_msg)
                service.set_error(error_msg)
                return False
    
    async def disconnect(self) -> bool:
        
        async with self.lock:
            if not self.current_service:
                self.logger.info("No active VPN connection to disconnect")
                return True
            
            try:
                if self.current_service.provider == VPNProvider.NORDVPN:
                    success = await self._disconnect_nordvpn()
                elif self.current_service.provider == VPNProvider.SURFSHARK:
                    success = await self._disconnect_surfshark()
                elif self.current_service.provider == VPNProvider.CUSTOM:
                    success = await self._disconnect_custom()
                else:
                    self.logger.error(f"Unsupported VPN provider: {self.current_service.provider}")
                    self.current_service.set_error(f"Unsupported VPN provider: {self.current_service.provider}")
                    return False
                
                if success:
                    self.current_service.set_disconnected()
                    self.logger.info(f"Disconnected from {self.current_service.name}")
                    self.current_service = None
                    return True
                else:
                    self.current_service.set_error("Failed to disconnect from VPN")
                    self.logger.error(f"Failed to disconnect from {self.current_service.name}")
                    return False
            
            except Exception as e:
                error_msg = f"Error disconnecting from VPN: {str(e)}"
                self.logger.error(error_msg)
                self.current_service.set_error(error_msg)
                return False
    
    async def check_connection(self) -> bool:
        
        if not self.current_service or self.current_service.status != VPNStatus.CONNECTED:
            return False
        
        try:
            
            response = requests.get("https://api.ipify.org?format=json", timeout=5)
            if response.status_code == 200:
                self.logger.debug(f"Current IP: {response.json()['ip']}")
                return True
            else:
                self.logger.error(f"Failed to check IP address: {response.status_code}")
                return False
        
        except Exception as e:
            self.logger.error(f"Error checking VPN connection: {str(e)}")
            return False
    
    async def get_current_ip(self) -> Optional[str]:
        
        try:
            response = requests.get("https://api.ipify.org?format=json", timeout=5)
            if response.status_code == 200:
                return response.json()["ip"]
            else:
                self.logger.error(f"Failed to get IP address: {response.status_code}")
                return None
        
        except Exception as e:
            self.logger.error(f"Error getting IP address: {str(e)}")
            return None
    
    async def get_current_region(self) -> Optional[str]:
        
        if not self.current_service or self.current_service.status != VPNStatus.CONNECTED:
            return None
        
        return self.current_service.current_region.code if self.current_service.current_region else None
    
    async def _connect_nordvpn(self, service: VPNService, region: VPNRegion) -> bool:
        
        try:
            
            if sys.platform == "win32":
                cmd = ["where", "nordvpn"]
            else:
                cmd = ["which", "nordvpn"]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error("NordVPN CLI not found")
                return False
            
            
            if "username" in service.auth_data and "password" in service.auth_data:
                login_cmd = ["nordvpn", "login", "--username", service.auth_data["username"], "--password", service.auth_data["password"]]
                subprocess.run(login_cmd, capture_output=True, text=True)
            
            
            connect_cmd = ["nordvpn", "connect", region.code]
            process = subprocess.Popen(connect_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            
            try:
                stdout, stderr = process.communicate(timeout=config.vpn.connection_timeout)
                if process.returncode == 0:
                    return True
                else:
                    self.logger.error(f"NordVPN connection error: {stderr}")
                    return False
            
            except subprocess.TimeoutExpired:
                process.kill()
                self.logger.error("NordVPN connection timeout")
                return False
        
        except Exception as e:
            self.logger.error(f"Error connecting to NordVPN: {str(e)}")
            return False
    
    async def _disconnect_nordvpn(self) -> bool:
        
        try:
            cmd = ["nordvpn", "disconnect"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        
        except Exception as e:
            self.logger.error(f"Error disconnecting from NordVPN: {str(e)}")
            return False
    
    async def _connect_surfshark(self, service: VPNService, region: VPNRegion) -> bool:
        
        
        
        self.logger.warning("Surfshark connection not implemented")
        return False
    
    async def _disconnect_surfshark(self) -> bool:
        
        
        self.logger.warning("Surfshark disconnection not implemented")
        return False
    
    async def _connect_custom(self, service: VPNService, region: VPNRegion) -> bool:
        
        try:
            
            if "connect_command" not in service.auth_data:
                self.logger.error("Missing connect_command in custom VPN configuration")
                return False
            
            
            connect_command = service.auth_data["connect_command"].replace("{region}", region.code)
            
            
            cmd = connect_command.split()
            self.connection_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            
            await asyncio.sleep(config.vpn.connection_timeout)
            
            
            if await self.check_connection():
                return True
            else:
                if self.connection_process:
                    self.connection_process.kill()
                self.connection_process = None
                return False
        
        except Exception as e:
            self.logger.error(f"Error connecting to custom VPN: {str(e)}")
            if self.connection_process:
                self.connection_process.kill()
            self.connection_process = None
            return False
    
    async def _disconnect_custom(self) -> bool:
        
        try:
            if not self.current_service:
                return True
            
            
            if "disconnect_command" not in self.current_service.auth_data:
                self.logger.error("Missing disconnect_command in custom VPN configuration")
                return False
            
            
            disconnect_command = self.current_service.auth_data["disconnect_command"]
            cmd = disconnect_command.split()
            subprocess.run(cmd, capture_output=True, text=True)
            
            
            if self.connection_process:
                self.connection_process.kill()
                self.connection_process = None
            
            
            await asyncio.sleep(2)
            if not await self.check_connection():
                return True
            else:
                return False
        
        except Exception as e:
            self.logger.error(f"Error disconnecting from custom VPN: {str(e)}")
            return False
    
    async def _add_standard_regions(self, service: VPNService):
        
        
        regions = [
            {"id": "in", "name": "India", "code": "IN"},
            {"id": "ar", "name": "Argentina", "code": "AR"},
            {"id": "tr", "name": "Turkey", "code": "TR"},
            {"id": "us", "name": "United States", "code": "US"},
            {"id": "gb", "name": "United Kingdom", "code": "GB"},
            {"id": "de", "name": "Germany", "code": "DE"},
            {"id": "jp", "name": "Japan", "code": "JP"},
            {"id": "sg", "name": "Singapore", "code": "SG"},
            {"id": "br", "name": "Brazil", "code": "BR"},
            {"id": "au", "name": "Australia", "code": "AU"}
        ]
        
        for region_data in regions:
            region = VPNRegion(**region_data)
            service.add_region(region)
    
    async def add_default_services(self):
        
        
        await self.add_service(
            provider=VPNProvider.NORDVPN,
            name="NordVPN",
            auth_data={}
        )
        
        
        await self.add_service(
            provider=VPNProvider.SURFSHARK,
            name="Surfshark",
            auth_data={}
        )
        
        
        await self.add_service(
            provider=VPNProvider.CUSTOM,
            name="Custom VPN",
            auth_data={
                "connect_command": "echo Connecting to {region}",
                "disconnect_command": "echo Disconnecting"
            }
        )
    
    async def load_vpn_services(self):
        
        try:
            if not os.path.exists(self.vpn_file):
                self.logger.info("VPN services file not found, starting with default services")
                return
            
            with open(self.vpn_file, "r") as f:
                services_data = json.load(f)
            
            
            pool = VPNServicePool()
            
            for service_data in services_data:
                
                regions_data = service_data.pop("regions", [])
                
                
                service = VPNService(**service_data)
                
                
                for region_data in regions_data:
                    region = VPNRegion(**region_data)
                    service.add_region(region)
                
                
                pool.add_service(service)
            
            self.vpn_pool = pool
            self.logger.info(f"Loaded {len(self.vpn_pool.services)} VPN services from file")
        
        except Exception as e:
            self.logger.error(f"Error loading VPN services: {str(e)}")
            
            self.vpn_pool = VPNServicePool()
    
    async def save_vpn_services(self):
        
        try:
            services_data = []
            
            for service in self.vpn_pool.services:
                
                service_dict = service.dict(exclude={"regions"})
                
                
                regions_data = [region.dict() for region in service.regions]
                service_dict["regions"] = regions_data
                
                services_data.append(service_dict)
            
            
            os.makedirs(os.path.dirname(self.vpn_file), exist_ok=True)
            with open(self.vpn_file, "w") as f:
                json.dump(services_data, f, indent=2)
            
            self.logger.debug(f"Saved {len(self.vpn_pool.services)} VPN services to file")
        
        except Exception as e:
            self.logger.error(f"Error saving VPN services: {str(e)}")
            raise 