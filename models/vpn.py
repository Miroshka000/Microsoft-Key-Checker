from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class VPNProvider(str, Enum):
    NORDVPN = "NordVPN"
    SURFSHARK = "Surfshark"
    CUSTOM = "Custom"

class VPNStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"

class VPNRegion(BaseModel):
    id: str  
    name: str  
    code: str  
    is_active: bool = True  
    
    @property
    def country_name(self) -> str:
        
        return self.name
    
    @property
    def country_code(self) -> str:
        
        return self.code.upper()

class VPNService(BaseModel):
    provider: VPNProvider
    name: str  
    auth_data: Dict = {}  
    regions: List[VPNRegion] = []  
    current_region: Optional[VPNRegion] = None  
    status: VPNStatus = VPNStatus.DISCONNECTED
    error_message: Optional[str] = None
    
    def add_region(self, region: VPNRegion):
        
        self.regions.append(region)
    
    def remove_region(self, region_id: str):
        
        self.regions = [reg for reg in self.regions if reg.id != region_id]
    
    def get_region_by_id(self, region_id: str) -> Optional[VPNRegion]:
        
        for region in self.regions:
            if region.id == region_id:
                return region
        return None
    
    def get_region_by_code(self, code: str) -> Optional[VPNRegion]:
        
        code = code.upper()
        for region in self.regions:
            if region.code.upper() == code:
                return region
        return None
    
    def set_current_region(self, region: VPNRegion):
        
        self.current_region = region
    
    def set_connected(self):
        
        self.status = VPNStatus.CONNECTED
    
    def set_disconnected(self):
        
        self.status = VPNStatus.DISCONNECTED
        self.current_region = None
    
    def set_connecting(self):
        
        self.status = VPNStatus.CONNECTING
    
    def set_error(self, message: str):
        
        self.status = VPNStatus.ERROR
        self.error_message = message

class VPNServicePool(BaseModel):
    services: List[VPNService] = []
    
    def add_service(self, service: VPNService):
        
        self.services.append(service)
    
    def remove_service(self, provider: VPNProvider, name: str):
        
        self.services = [svc for svc in self.services if not (svc.provider == provider and svc.name == name)]
    
    def get_service_by_provider(self, provider: VPNProvider) -> Optional[VPNService]:
        
        for service in self.services:
            if service.provider == provider:
                return service
        return None
    
    def get_service_by_name(self, name: str) -> Optional[VPNService]:
        
        for service in self.services:
            if service.name == name:
                return service
        return None 