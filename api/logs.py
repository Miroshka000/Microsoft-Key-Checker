import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import LOGS_DIR

router = APIRouter()
logger = logging.getLogger(__name__)

class LogEntry(BaseModel):
    level: str
    time: str
    message: str
    logger_name: str
    file: Optional[str] = None
    line: Optional[int] = None

class LogFileInfo(BaseModel):
    name: str
    size: int
    created_at: str
    updated_at: str

@router.get("/files", response_model=List[LogFileInfo])
async def get_log_files():
    
    try:
        
        if not os.path.exists(LOGS_DIR):
            return []
        
        
        log_files = []
        for file_name in os.listdir(LOGS_DIR):
            if file_name.endswith(".log"):
                file_path = os.path.join(LOGS_DIR, file_name)
                stat = os.stat(file_path)
                
                log_files.append({
                    "name": file_name,
                    "size": stat.st_size,
                    "created_at": stat.st_ctime,
                    "updated_at": stat.st_mtime
                })
        
        return log_files
    
    except Exception as e:
        logger.error(f"Error getting log files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting log files: {str(e)}")

@router.get("/files/{file_name}", response_model=List[LogEntry])
async def get_log_file_content(
    file_name: str,
    limit: int = Query(100, description="Maximum number of log entries to return"),
    offset: int = Query(0, description="Number of log entries to skip"),
    level: Optional[str] = Query(None, description="Filter logs by level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
):
    
    try:
        
        file_path = os.path.join(LOGS_DIR, file_name)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Log file {file_name} not found")
        
        
        with open(file_path, "r") as f:
            lines = f.readlines()
        
        
        log_entries = []
        for line in lines:
            try:
                
                parts = line.strip().split(" - ", 3)
                if len(parts) >= 4:
                    time_str, level_str, logger_name, message = parts
                    
                    
                    if level and level.upper() != level_str.upper():
                        continue
                    
                    
                    file_info = None
                    line_number = None
                    
                    if " (file: " in message:
                        message_parts = message.split(" (file: ", 1)
                        message = message_parts[0]
                        file_info_str = message_parts[1].strip(")")
                        
                        if ", line: " in file_info_str:
                            file_info_parts = file_info_str.split(", line: ", 1)
                            file_info = file_info_parts[0]
                            try:
                                line_number = int(file_info_parts[1])
                            except ValueError:
                                pass
                    
                    log_entries.append({
                        "level": level_str,
                        "time": time_str,
                        "message": message,
                        "logger_name": logger_name,
                        "file": file_info,
                        "line": line_number
                    })
            except Exception as parse_error:
                
                continue
        
        
        paginated_entries = log_entries[offset:offset + limit]
        
        return paginated_entries
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error reading log file {file_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading log file {file_name}: {str(e)}")

@router.get("/files/{file_name}/download")
async def download_log_file(file_name: str):
    
    try:
        
        file_path = os.path.join(LOGS_DIR, file_name)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Log file {file_name} not found")
        
        
        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="text/plain"
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error downloading log file {file_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading log file {file_name}: {str(e)}")

@router.delete("/files/{file_name}")
async def delete_log_file(file_name: str):
    
    try:
        
        file_path = os.path.join(LOGS_DIR, file_name)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Log file {file_name} not found")
        
        
        os.remove(file_path)
        
        return {"message": f"Log file {file_name} deleted"}
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error deleting log file {file_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting log file {file_name}: {str(e)}")

@router.delete("/clear")
async def clear_log_files():
    
    try:
        
        if not os.path.exists(LOGS_DIR):
            return {"message": "No log files to delete"}
        
        
        deleted_count = 0
        for file_name in os.listdir(LOGS_DIR):
            if file_name.endswith(".log"):
                file_path = os.path.join(LOGS_DIR, file_name)
                os.remove(file_path)
                deleted_count += 1
        
        return {"message": f"Deleted {deleted_count} log files"}
    
    except Exception as e:
        logger.error(f"Error clearing log files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clearing log files: {str(e)}") 