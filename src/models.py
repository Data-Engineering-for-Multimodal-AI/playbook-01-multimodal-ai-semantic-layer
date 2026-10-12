"""
Data models and record contract for granite-lite semantic layer

Copyright (c) 2025-2026
Data Engineering for Multimodal AI

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
import re

@dataclass
class RecordContract:
    """Enforces the required record contract for all modalities"""
    entity_id: str
    encounter_id: str
    modality: str  # 'image', 'note', 'vitals'
    timestamp: datetime
    provenance: str  # source system or process
    quality: float  # 0.0 to 1.0
    
    def __post_init__(self):
        """Validate contract fields"""
        if not self.entity_id or not self.encounter_id:
            raise ValueError("entity_id and encounter_id are required")
        if self.modality not in ['image', 'note', 'vitals']:
            raise ValueError("modality must be 'image', 'note', or 'vitals'")
        if not (0.0 <= self.quality <= 1.0):
            raise ValueError("quality must be between 0.0 and 1.0")

@dataclass
class ImageRecord(RecordContract):
    """Image modality record with file path"""
    file_path: str
    label_vector: List[int]  # 14-element binary array for conditions

@dataclass
class NoteRecord(RecordContract):
    """Clinical note modality record with text content"""
    content: str
    key_tokens: List[str]  # extracted clinical terms

@dataclass
class VitalsRecord(RecordContract):
    """Vitals modality record with time series data"""
    vitals_data: List[Dict[str, Any]]  # list of {ts, hr, spo2, rr} records

@dataclass
class FusedEvent:
    """Fused event combining all modalities for an encounter"""
    encounter_id: str
    diagnosis: str
    confidence: float
    evidence: List[Dict[str, Any]]
    lineage: Dict[str, Any]
    timestamp: datetime

class ContractValidator:
    """Validates record contracts and tracks violations"""
    
    def __init__(self):
        self.violations = []
    
    def validate_record(self, record: RecordContract) -> bool:
        """Validate a record against the contract"""
        try:
            record.__post_init__()
            return True
        except ValueError as e:
            self.violations.append({
                'record_type': type(record).__name__,
                'entity_id': getattr(record, 'entity_id', 'unknown'),
                'encounter_id': getattr(record, 'encounter_id', 'unknown'),
                'error': str(e),
                'timestamp': datetime.now()
            })
            return False
    
    def get_violation_count(self) -> int:
        return len(self.violations)
    
    def get_violations(self) -> List[Dict[str, Any]]:
        return self.violations.copy()

def parse_filename_to_encounter(filename: str) -> tuple[str, List[int]]:
    """Parse ChestMNIST filename to extract encounter_id and label vector"""
    # Format: chestmnist_sample_XXX_label_[binary_array].png
    pattern = r'chestmnist_sample_(\d+)_label_\[([0-9\s,]+)\]\.png'
    match = re.match(pattern, filename)
    
    if not match:
        raise ValueError(f"Invalid filename format: {filename}")
    
    sample_num = int(match.group(1))
    encounter_id = f"enc_{sample_num + 1:05d}"  # enc_00001 to enc_00050
    
    # Parse binary array - handle spaces between numbers
    binary_str = match.group(2)
    # Split by spaces and filter out empty strings
    label_parts = [x for x in binary_str.split() if x]
    label_vector = [int(x) for x in label_parts]
    
    if len(label_vector) != 14:
        raise ValueError(f"Expected 14 labels, got {len(label_vector)} from '{binary_str}'")
    
    return encounter_id, label_vector
