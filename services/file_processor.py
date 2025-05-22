import csv
import logging
import os
import pandas as pd
from typing import List, Optional, Dict, Any
from pathlib import Path

from models.key import Key, KeyCheckResult, KeyStatus
from config import DATA_DIR

class FileProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.output_dir = os.path.join(DATA_DIR, "results")
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def parse_keys_from_text(self, text: str) -> List[Key]:
        
        try:
            keys = []
            lines = text.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                key = Key(key=line)
                keys.append(key)
            
            self.logger.info(f"Parsed {len(keys)} keys from text input")
            return keys
        
        except Exception as e:
            self.logger.error(f"Error parsing keys from text: {str(e)}")
            return []
    
    async def parse_keys_from_csv(self, file_path: str) -> List[Key]:
        
        try:
            keys = []
            
            
            if not os.path.exists(file_path):
                self.logger.error(f"CSV file not found: {file_path}")
                return []
            
            
            df = pd.read_csv(file_path)
            
            
            key_column = None
            region_column = None
            
            for col in df.columns:
                if col.lower() in ['key', 'keys', 'product_key', 'license_key']:
                    key_column = col
                elif col.lower() in ['region', 'country', 'country_code']:
                    region_column = col
            
            if not key_column:
                self.logger.error(f"Key column not found in CSV file: {file_path}")
                return []
            
            
            for _, row in df.iterrows():
                key_value = str(row[key_column]).strip()
                
                if not key_value:
                    continue
                
                region = None
                if region_column and pd.notna(row[region_column]):
                    region = str(row[region_column]).strip()
                
                key = Key(key=key_value, region=region)
                keys.append(key)
            
            self.logger.info(f"Parsed {len(keys)} keys from CSV file: {file_path}")
            return keys
        
        except Exception as e:
            self.logger.error(f"Error parsing keys from CSV file: {str(e)}")
            return []
    
    async def parse_keys_from_txt(self, file_path: str) -> List[Key]:
        
        try:
            keys = []
            
            
            if not os.path.exists(file_path):
                self.logger.error(f"TXT file not found: {file_path}")
                return []
            
            
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                
                parts = line.split(',')
                if len(parts) >= 2:
                    key_value = parts[0].strip()
                    region = parts[1].strip()
                    key = Key(key=key_value, region=region)
                else:
                    key = Key(key=line)
                
                keys.append(key)
            
            self.logger.info(f"Parsed {len(keys)} keys from TXT file: {file_path}")
            return keys
        
        except Exception as e:
            self.logger.error(f"Error parsing keys from TXT file: {str(e)}")
            return []
    
    async def save_results_to_csv(self, results: List[KeyCheckResult], file_path: Optional[str] = None) -> str:
        
        try:
            
            if not file_path:
                file_name = f"key_check_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
                file_path = os.path.join(self.output_dir, file_name)
            
            
            data = []
            for result in results:
                data.append({
                    'key': result.key.formatted_key,
                    'status': result.status,
                    'error_message': result.error_message,
                    'region': result.key.region,
                    'region_used': result.region_used,
                    'is_global': result.is_global,
                    'account_used': result.account_used,
                    'check_time': result.check_time,
                })
            
            df = pd.DataFrame(data)
            
            
            df.to_csv(file_path, index=False)
            
            self.logger.info(f"Saved {len(results)} results to CSV file: {file_path}")
            return file_path
        
        except Exception as e:
            self.logger.error(f"Error saving results to CSV file: {str(e)}")
            return ""
    
    async def save_valid_keys_to_txt(self, results: List[KeyCheckResult], file_path: Optional[str] = None) -> str:
        
        return await self._save_keys_by_status(results, KeyStatus.VALID, file_path)
    
    async def save_used_keys_to_txt(self, results: List[KeyCheckResult], file_path: Optional[str] = None) -> str:
        
        return await self._save_keys_by_status(results, KeyStatus.USED, file_path)
    
    async def save_invalid_keys_to_txt(self, results: List[KeyCheckResult], file_path: Optional[str] = None) -> str:
        
        return await self._save_keys_by_status(results, KeyStatus.INVALID, file_path)
    
    async def save_region_error_keys_to_txt(self, results: List[KeyCheckResult], file_path: Optional[str] = None) -> str:
        
        return await self._save_keys_by_status(results, KeyStatus.REGION_ERROR, file_path)
    
    async def save_error_keys_to_txt(self, results: List[KeyCheckResult], file_path: Optional[str] = None) -> str:
        
        return await self._save_keys_by_status(results, KeyStatus.ERROR, file_path)
    
    async def _save_keys_by_status(self, results: List[KeyCheckResult], status: KeyStatus, file_path: Optional[str] = None) -> str:
        
        try:
            
            if not file_path:
                file_name = f"keys_{status.value}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.txt"
                file_path = os.path.join(self.output_dir, file_name)
            
            
            filtered_results = [result for result in results if result.status == status]
            
            
            with open(file_path, 'w') as f:
                for result in filtered_results:
                    f.write(f"{result.key.formatted_key}")
                    if result.error_message:
                        f.write(f",{result.error_message}")
                    elif result.region_used:
                        f.write(f",{result.region_used}")
                    f.write("\n")
            
            self.logger.info(f"Saved {len(filtered_results)} {status.value} keys to TXT file: {file_path}")
            return file_path
        
        except Exception as e:
            self.logger.error(f"Error saving {status.value} keys to TXT file: {str(e)}")
            return "" 