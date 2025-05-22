from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models.vpn import VPNRegion, VPNService, VPNProvider, VPNStatus
from services.vpn_manager import VPNManager

router = APIRouter()

class VPNServiceCreate(BaseModel):
    provider: VPNProvider
    name: str
    auth_data: Dict[str, Any] = Field(default_factory=dict)

class VPNRegionCreate(BaseModel):
    region_id: str
    name: str
    code: str

class VPNServiceResponse(BaseModel):
    provider: VPNProvider
    name: str
    status: VPNStatus
    current_region: Optional[str] = None
    regions_count: int

class VPNRegionResponse(BaseModel):
    id: str
    name: str
    code: str
    is_active: bool

class VPNStatusResponse(BaseModel):
    connected: bool
    current_service: Optional[str] = None
    current_region: Optional[str] = None
    ip_address: Optional[str] = None

async def get_vpn_manager():
    vpn_manager = VPNManager()
    await vpn_manager.initialize()
    return vpn_manager

@router.get("/services", response_model=List[VPNServiceResponse])
async def get_vpn_services(
    vpn_manager: VPNManager = Depends(get_vpn_manager)
):
    
    services = vpn_manager.vpn_pool.services
    
    
    return [
        {
            "provider": service.provider,
            "name": service.name,
            "status": service.status,
            "current_region": service.current_region.code if service.current_region else None,
            "regions_count": len(service.regions)
        }
        for service in services
    ]

@router.post("/services", response_model=VPNServiceResponse)
async def create_vpn_service(
    service_data: VPNServiceCreate,
    vpn_manager: VPNManager = Depends(get_vpn_manager)
):
    
    service = await vpn_manager.add_service(
        provider=service_data.provider,
        name=service_data.name,
        auth_data=service_data.auth_data
    )
    
    return {
        "provider": service.provider,
        "name": service.name,
        "status": service.status,
        "current_region": service.current_region.code if service.current_region else None,
        "regions_count": len(service.regions)
    }

@router.get("/services/{service_name}", response_model=VPNServiceResponse)
async def get_vpn_service(
    service_name: str,
    vpn_manager: VPNManager = Depends(get_vpn_manager)
):
    
    service = await vpn_manager.get_service(service_name)
    
    if not service:
        raise HTTPException(status_code=404, detail=f"VPN service with name {service_name} not found")
    
    return {
        "provider": service.provider,
        "name": service.name,
        "status": service.status,
        "current_region": service.current_region.code if service.current_region else None,
        "regions_count": len(service.regions)
    }

@router.delete("/services/{service_name}")
async def delete_vpn_service(
    service_name: str,
    vpn_manager: VPNManager = Depends(get_vpn_manager)
):
    
    service = await vpn_manager.get_service(service_name)
    
    if not service:
        raise HTTPException(status_code=404, detail=f"VPN service with name {service_name} not found")
    
    success = await vpn_manager.remove_service(service.provider, service_name)
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to delete VPN service with name {service_name}")
    
    return {"message": f"VPN service with name {service_name} deleted"}

@router.get("/services/{service_name}/regions", response_model=List[VPNRegionResponse])
async def get_vpn_service_regions(
    service_name: str,
    vpn_manager: VPNManager = Depends(get_vpn_manager)
):
    
    service = await vpn_manager.get_service(service_name)
    
    if not service:
        raise HTTPException(status_code=404, detail=f"VPN service with name {service_name} not found")
    
    
    return [
        {
            "id": region.id,
            "name": region.name,
            "code": region.code,
            "is_active": region.is_active
        }
        for region in service.regions
    ]

@router.post("/services/{service_name}/regions", response_model=VPNRegionResponse)
async def add_vpn_service_region(
    service_name: str,
    region_data: VPNRegionCreate,
    vpn_manager: VPNManager = Depends(get_vpn_manager)
):
    
    region = await vpn_manager.add_region(
        service_name=service_name,
        region_id=region_data.region_id,
        region_name=region_data.name,
        region_code=region_data.code
    )
    
    if not region:
        raise HTTPException(status_code=404, detail=f"VPN service with name {service_name} not found")
    
    return {
        "id": region.id,
        "name": region.name,
        "code": region.code,
        "is_active": region.is_active
    }

@router.delete("/services/{service_name}/regions/{region_id}")
async def delete_vpn_service_region(
    service_name: str,
    region_id: str,
    vpn_manager: VPNManager = Depends(get_vpn_manager)
):
    
    success = await vpn_manager.remove_region(service_name, region_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"VPN service with name {service_name} or region with ID {region_id} not found")
    
    return {"message": f"Region with ID {region_id} deleted from VPN service {service_name}"}

@router.post("/connect/{service_name}/{region_code}")
async def connect_vpn(
    service_name: str,
    region_code: str,
    vpn_manager: VPNManager = Depends(get_vpn_manager)
):
    
    success = await vpn_manager.connect(service_name, region_code)
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to connect to VPN service {service_name} with region {region_code}")
    
    return {"message": f"Connected to VPN service {service_name} with region {region_code}"}

@router.post("/disconnect")
async def disconnect_vpn(
    vpn_manager: VPNManager = Depends(get_vpn_manager)
):
    
    success = await vpn_manager.disconnect()
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to disconnect from VPN")
    
    return {"message": "Disconnected from VPN"}

@router.get("/status", response_model=VPNStatusResponse)
async def get_vpn_status(
    vpn_manager: VPNManager = Depends(get_vpn_manager)
):
    
    connected = await vpn_manager.check_connection()
    ip_address = await vpn_manager.get_current_ip()
    region = await vpn_manager.get_current_region()
    
    return {
        "connected": connected,
        "current_service": vpn_manager.current_service.name if vpn_manager.current_service else None,
        "current_region": region,
        "ip_address": ip_address
    } 