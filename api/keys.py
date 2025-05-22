import os
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import logging

from models.key import Key, KeyStatus, KeyCheckResult
from services.key_checker import KeyChecker
from services.account_manager import AccountManager
from services.vpn_manager import VPNManager
from services.file_processor import FileProcessor
from config import config, DATA_DIR

router = APIRouter()

account_manager = None
vpn_manager = None
key_checker = None
file_processor = None

class KeyInput(BaseModel):
    key: str
    region: Optional[str] = None

class KeysInput(BaseModel):
    keys: List[KeyInput]
    regions: Optional[List[str]] = None

class KeyCheckResponse(BaseModel):
    key: str
    status: KeyStatus
    error_message: Optional[str] = None
    region_used: Optional[str] = None
    is_global: bool = False
    check_id: Optional[str] = None

class KeyCheckStatusResponse(BaseModel):
    status: str
    stage: str
    progress: int
    message: str
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

class BatchStatusResponse(BaseModel):
    batch_id: str
    status: str
    progress: float
    total_keys: int
    processed_keys: int
    valid_count: int
    used_count: int
    invalid_count: int
    region_error_count: int
    error_count: int

class BatchCreateResponse(BaseModel):
    batch_id: str
    message: str

async def get_services():
    global account_manager, vpn_manager, key_checker, file_processor
    if account_manager is None:
        account_manager = AccountManager()
        await account_manager.initialize()
        vpn_manager = VPNManager()
        await vpn_manager.initialize()
        key_checker = KeyChecker(account_manager, vpn_manager)
        await key_checker.initialize()
        file_processor = FileProcessor()
    return {
        "account_manager": account_manager,
        "vpn_manager": vpn_manager,
        "key_checker": key_checker,
        "file_processor": file_processor
    }

@router.post("/check", response_model=KeyCheckResponse)
async def check_key(
    key_input: KeyInput,
    services: Dict[str, Any] = Depends(get_services)
):
    
    key_checker = services["key_checker"]
    
    
    key = Key(key=key_input.key, region=key_input.region)
    
    
    result = await key_checker.check_key(key)
    
    
    return {
        "key": result.key.formatted_key,
        "status": result.status,
        "error_message": result.error_message,
        "region_used": result.region_used,
        "is_global": result.is_global,
        "check_id": result.check_id
    }

@router.post("/check-batch", response_model=BatchCreateResponse)
async def check_keys_batch(
    keys_input: KeysInput,
    background_tasks: BackgroundTasks,
    services: Dict[str, Any] = Depends(get_services)
):
    
    key_checker = services["key_checker"]
    
    
    keys = [Key(key=key_input.key, region=key_input.region) for key_input in keys_input.keys]
    
    
    batch_id = await key_checker.check_keys_batch(keys, keys_input.regions)
    
    return {
        "batch_id": batch_id,
        "message": f"Batch check started with {len(keys)} keys"
    }

@router.get("/batch/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    services: Dict[str, Any] = Depends(get_services)
):
    
    key_checker = services["key_checker"]
    
    
    status = await key_checker.get_batch_status(batch_id)
    
    if status["status"] == "not_found":
        raise HTTPException(status_code=404, detail=f"Batch with ID {batch_id} not found")
    
    return {
        "batch_id": batch_id,
        "status": status["status"],
        "progress": status["progress"],
        "total_keys": status["total_keys"],
        "processed_keys": status["processed_keys"],
        "valid_count": status["valid_keys"],
        "used_count": status["used_keys"],
        "invalid_count": status["invalid_keys"],
        "region_error_count": status["region_error_keys"],
        "error_count": status["error_keys"]
    }

@router.get("/batch/{batch_id}/results")
async def get_batch_results(
    batch_id: str,
    services: Dict[str, Any] = Depends(get_services)
):
    
    key_checker = services["key_checker"]
    file_processor = services["file_processor"]
    
    
    results = await key_checker.get_batch_results(batch_id)
    
    if not results:
        raise HTTPException(status_code=404, detail=f"Batch with ID {batch_id} not found or has no results")
    
    
    return [
        {
            "key": result.key.formatted_key,
            "status": result.status,
            "error_message": result.error_message,
            "region_used": result.region_used,
            "is_global": result.is_global
        }
        for result in results
    ]

@router.get("/batch/{batch_id}/export/{format}/{status}")
async def export_batch_results(
    batch_id: str,
    format: str,
    status: str,
    services: Dict[str, Any] = Depends(get_services)
):
    
    key_checker = services["key_checker"]
    file_processor = services["file_processor"]
    
    
    if format not in ["csv", "txt"]:
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'txt'")
    
    
    try:
        key_status = KeyStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    
    results = await key_checker.get_batch_results(batch_id)
    
    if not results:
        raise HTTPException(status_code=404, detail=f"Batch with ID {batch_id} not found or has no results")
    
    
    if status != "all":
        results = [result for result in results if result.status == key_status]
    
    
    file_name = f"keys_{status}_{batch_id}.{format}"
    file_path = os.path.join(DATA_DIR, "exports", file_name)
    
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    
    if format == "csv":
        await file_processor.save_results_to_csv(results, file_path)
    else:  
        if status == "valid":
            await file_processor.save_valid_keys_to_txt(results, file_path)
        elif status == "used":
            await file_processor.save_used_keys_to_txt(results, file_path)
        elif status == "invalid":
            await file_processor.save_invalid_keys_to_txt(results, file_path)
        elif status == "region_error":
            await file_processor.save_region_error_keys_to_txt(results, file_path)
        elif status == "error":
            await file_processor.save_error_keys_to_txt(results, file_path)
        else:
            
            with open(file_path, "w") as f:
                for result in results:
                    f.write(f"{result.key.formatted_key}\n")
    
    
    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type="application/octet-stream"
    )

@router.post("/upload")
async def upload_keys(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    region: Optional[str] = Form(None),
    services: Dict[str, Any] = Depends(get_services)
):
    
    key_checker = services["key_checker"]
    file_processor = services["file_processor"]
    
    
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    
    temp_file_path = os.path.join(DATA_DIR, "uploads", file.filename)
    os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
    
    with open(temp_file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    
    if file_extension == ".csv":
        keys = await file_processor.parse_keys_from_csv(temp_file_path)
    elif file_extension == ".txt":
        keys = await file_processor.parse_keys_from_txt(temp_file_path)
    else:
        os.remove(temp_file_path)
        raise HTTPException(status_code=400, detail="File must be .csv or .txt")
    
    
    if region:
        for key in keys:
            key.region = region
    
    
    batch_id = await key_checker.check_keys_batch(keys)
    
    return {
        "batch_id": batch_id,
        "message": f"Batch check started with {len(keys)} keys from file {file.filename}"
    }

@router.get("/status/{check_id}", response_model=KeyCheckStatusResponse)
async def get_key_check_status(
    check_id: str,
    services: Dict[str, Any] = Depends(get_services)
):
    
    key_checker = services["key_checker"]
    
    try:
        
        logging.info(f"Получен запрос статуса для ID: {check_id}")
        
        
        status = await key_checker.get_key_status(check_id)
        
        
        if status["status"] == "not_found":
            logging.warning(f"Статус проверки не найден: {check_id}")
            raise HTTPException(
                status_code=404, 
                detail=f"Check with ID {check_id} not found"
            )
        
        logging.info(f"Возвращаем статус для ID: {check_id}, статус: {status['status']}, прогресс: {status['progress']}%")
        return status
    except HTTPException:
        
        raise
    except Exception as e:
        
        logging.error(f"Ошибка при получении статуса для ID {check_id}: {str(e)}")
        
        return {
            "status": "error",
            "stage": "error",
            "progress": 0,
            "message": "Произошла ошибка при получении статуса",
            "error_message": str(e),
            "result": None
        } 