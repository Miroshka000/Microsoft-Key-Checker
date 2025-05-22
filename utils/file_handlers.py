import os
import csv
import json
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

async def read_file(file_path: str) -> str:
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        raise

async def write_file(file_path: str, content: str) -> bool:
    
    try:
        
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Error writing to file {file_path}: {str(e)}")
        return False

async def read_json(file_path: str) -> Dict[str, Any]:
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading JSON file {file_path}: {str(e)}")
        return {}

async def write_json(file_path: str, data: Dict[str, Any], indent: int = 4) -> bool:
    
    try:
        
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent)
        return True
    except Exception as e:
        logger.error(f"Error writing JSON to file {file_path}: {str(e)}")
        return False

async def parse_csv(file_path: str, has_header: bool = True) -> Tuple[List[str], List[Dict[str, str]]]:
    
    try:
        with open(file_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            
            
            headers = next(reader) if has_header else []
            
            
            data = []
            for row in reader:
                if has_header:
                    
                    row_dict = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
                    data.append(row_dict)
                else:
                    
                    data.append(row)
            
            return headers, data
    except Exception as e:
        logger.error(f"Error parsing CSV file {file_path}: {str(e)}")
        return [], []

async def write_csv(file_path: str, data: List[Dict[str, Any]], headers: Optional[List[str]] = None) -> bool:
    
    try:
        
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        
        if not headers and data and isinstance(data[0], dict):
            headers = list(data[0].keys())
        
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            
            if headers:
                writer.writerow(headers)
            
            
            for row in data:
                if isinstance(row, dict):
                    
                    writer.writerow([row.get(h, '') for h in headers])
                else:
                    
                    writer.writerow(row)
        
        return True
    except Exception as e:
        logger.error(f"Error writing CSV to file {file_path}: {str(e)}")
        return False

async def parse_txt(file_path: str) -> List[str]:
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f.readlines()]
    except Exception as e:
        logger.error(f"Error parsing TXT file {file_path}: {str(e)}")
        return []

async def write_txt(file_path: str, lines: List[str]) -> bool:
    
    try:
        
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in lines:
                f.write(f"{line}\n")
        return True
    except Exception as e:
        logger.error(f"Error writing TXT to file {file_path}: {str(e)}")
        return False

async def file_exists(file_path: str) -> bool:
    
    return os.path.isfile(file_path)

async def directory_exists(dir_path: str) -> bool:
    
    return os.path.isdir(dir_path)

async def create_directory(dir_path: str) -> bool:
    
    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {dir_path}: {str(e)}")
        return False

async def list_files(dir_path: str, extension: Optional[str] = None) -> List[str]:
    
    try:
        if not os.path.isdir(dir_path):
            logger.error(f"Directory {dir_path} does not exist")
            return []
        
        files = os.listdir(dir_path)
        
        if extension:
            
            extension = extension.lower()
            if not extension.startswith('.'):
                extension = f".{extension}"
            
            files = [f for f in files if os.path.isfile(os.path.join(dir_path, f)) and f.lower().endswith(extension)]
        else:
            
            files = [f for f in files if os.path.isfile(os.path.join(dir_path, f))]
        
        return files
    except Exception as e:
        logger.error(f"Error listing files in directory {dir_path}: {str(e)}")
        return [] 