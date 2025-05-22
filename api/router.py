from fastapi import APIRouter
from api.keys import router as keys_router
from api.accounts import router as accounts_router
from api.vpn import router as vpn_router
from api.logs import router as logs_router

router = APIRouter()

router.include_router(keys_router, prefix="/keys", tags=["keys"])
router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
router.include_router(vpn_router, prefix="/vpn", tags=["vpn"])
router.include_router(logs_router, prefix="/logs", tags=["logs"])

@router.get("/", tags=["info"])
async def root():
    
    return {
        "app": "Microsoft Key Checker",
        "version": "1.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "endpoints": {
            "keys": "/keys",
            "accounts": "/accounts",
            "vpn": "/vpn",
            "logs": "/logs"
        }
    }

@router.get("/health", tags=["info"])
async def health_check():
    
    return {"status": "ok"} 