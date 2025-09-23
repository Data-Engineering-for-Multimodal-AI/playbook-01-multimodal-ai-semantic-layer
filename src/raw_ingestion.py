"""
Raw data ingestion pipeline - processes existing raw data files
"""

import os
import glob
import csv
from datetime import datetime
from typing import List, Dict, Any
import duckdb

from models import (
    ImageRecord, NoteRecord, VitalsRecord, 
    ContractValidator, parse_filename_to_encounter
)

class RawDataIngestionPipeline:
    """Handles ingestion of raw data files with contract validation"""
    
    def __init__(self, db_path: str = "data/processed/granite_lite.db"):
        self.db_path = db_path
        self.validator = ContractValidator()
        self.conn = duckdb.connect(db_path)
        self._create_manifest_tables()
    
    def _create_manifest_tables(self):
        """Create manifest tables in DuckDB"""
        # Image manifest
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS image_manifest (
                entity_id VARCHAR,
                encounter_id VARCHAR,
                modality VARCHAR,
                timestamp TIMESTAMP,
                provenance VARCHAR,
                quality FLOAT,
                file_path VARCHAR,
                label_vector VARCHAR
            )
        """)
        
        # Note manifest
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS note_manifest (
                entity_id VARCHAR,
                encounter_id VARCHAR,
                modality VARCHAR,
                timestamp TIMESTAMP,
                provenance VARCHAR,
                quality FLOAT,
                content TEXT,
                key_tokens VARCHAR
            )
        """)
        
        # Vitals manifest
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS vitals_manifest (
                entity_id VARCHAR,
                encounter_id VARCHAR,
                modality VARCHAR,
                timestamp TIMESTAMP,
                provenance VARCHAR,
                quality FLOAT,
                file_path VARCHAR
            )
        """)
        
        # Curated manifest (unified view)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS curated_manifest (
                encounter_id VARCHAR,
                entity_id VARCHAR,
                image_path VARCHAR,
                note_content TEXT,
                vitals_path VARCHAR,
                image_quality FLOAT,
                note_quality FLOAT,
                vitals_quality FLOAT,
                created_at TIMESTAMP
            )
        """)
    
    def ingest_images(self, images_dir: str) -> List[ImageRecord]:
        """Ingest image data from directory"""
        image_files = glob.glob(os.path.join(images_dir, "*.png"))
        image_records = []
        
        for image_file in sorted(image_files):
            filename = os.path.basename(image_file)
            try:
                encounter_id, label_vector = parse_filename_to_encounter(filename)
                
                record = ImageRecord(
                    entity_id=f"entity_{encounter_id}",
                    encounter_id=encounter_id,
                    modality="image",
                    timestamp=datetime.now(),
                    provenance="chestmnist_dataset",
                    quality=0.95,  # High quality for medical images
                    file_path=image_file,
                    label_vector=label_vector
                )
                
                if self.validator.validate_record(record):
                    image_records.append(record)
                    self._insert_image_record(record)
                    
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                continue
        
        return image_records
    
    def ingest_notes(self, notes_dir: str) -> List[NoteRecord]:
        """Ingest clinical notes from directory"""
        note_files = glob.glob(os.path.join(notes_dir, "*_note.txt"))
        note_records = []
        
        for note_file in sorted(note_files):
            filename = os.path.basename(note_file)
            try:
                # Extract encounter_id from filename (e.g., enc_00001_note.txt)
                encounter_id = filename.replace("_note.txt", "")
                
                # Read note content
                with open(note_file, 'r') as f:
                    content = f.read().strip()
                
                # Extract key tokens (simple keyword extraction)
                key_tokens = self._extract_key_tokens(content)
                
                record = NoteRecord(
                    entity_id=f"entity_{encounter_id}",
                    encounter_id=encounter_id,
                    modality="note",
                    timestamp=datetime.now(),
                    provenance="raw_data_files",
                    quality=0.85,  # Raw data quality
                    content=content,
                    key_tokens=key_tokens
                )
                
                if self.validator.validate_record(record):
                    note_records.append(record)
                    self._insert_note_record(record)
                    
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                continue
        
        return note_records
    
    def ingest_vitals(self, vitals_dir: str) -> List[VitalsRecord]:
        """Ingest vital signs from CSV files"""
        vitals_files = glob.glob(os.path.join(vitals_dir, "*_vitals.csv"))
        vitals_records = []
        
        for vitals_file in sorted(vitals_files):
            filename = os.path.basename(vitals_file)
            try:
                # Extract encounter_id from filename (e.g., enc_00001_vitals.csv)
                encounter_id = filename.replace("_vitals.csv", "")
                
                # Read vitals data
                vitals_data = []
                with open(vitals_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        vitals_data.append(row)
                
                record = VitalsRecord(
                    entity_id=f"entity_{encounter_id}",
                    encounter_id=encounter_id,
                    modality="vitals",
                    timestamp=datetime.now(),
                    provenance="raw_data_files",
                    quality=0.90,  # Raw data quality
                    vitals_data=vitals_data
                )
                
                if self.validator.validate_record(record):
                    vitals_records.append(record)
                    self._insert_vitals_record(record, vitals_file)
                    
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                continue
        
        return vitals_records
    
    def _extract_key_tokens(self, content: str) -> List[str]:
        """Extract clinical key tokens from note content"""
        clinical_terms = [
            "opacity", "consolidation", "infiltrate", "pneumonia", "atelectasis",
            "cardiomegaly", "effusion", "mass", "nodule", "pneumothorax",
            "edema", "emphysema", "fibrosis", "pleural", "hernia"
        ]
        
        tokens = []
        for term in clinical_terms:
            if term.lower() in content.lower():
                tokens.append(term)
        return tokens
    
    def _insert_image_record(self, record: ImageRecord):
        """Insert image record into manifest"""
        self.conn.execute("""
            INSERT INTO image_manifest 
            (entity_id, encounter_id, modality, timestamp, provenance, quality, file_path, label_vector)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.entity_id, record.encounter_id, record.modality,
            record.timestamp, record.provenance, record.quality,
            record.file_path, str(record.label_vector)
        ))
    
    def _insert_note_record(self, record: NoteRecord):
        """Insert note record into manifest"""
        self.conn.execute("""
            INSERT INTO note_manifest 
            (entity_id, encounter_id, modality, timestamp, provenance, quality, content, key_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.entity_id, record.encounter_id, record.modality,
            record.timestamp, record.provenance, record.quality,
            record.content, str(record.key_tokens)
        ))
    
    def _insert_vitals_record(self, record: VitalsRecord, file_path: str):
        """Insert vitals record into manifest"""
        self.conn.execute("""
            INSERT INTO vitals_manifest 
            (entity_id, encounter_id, modality, timestamp, provenance, quality, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            record.entity_id, record.encounter_id, record.modality,
            record.timestamp, record.provenance, record.quality, file_path
        ))
    
    def create_curated_manifest(self):
        """Create unified curated manifest joining all modalities"""
        self.conn.execute("""
            INSERT INTO curated_manifest
            SELECT 
                i.encounter_id,
                i.entity_id,
                i.file_path as image_path,
                n.content as note_content,
                v.file_path as vitals_path,
                i.quality as image_quality,
                n.quality as note_quality,
                v.quality as vitals_quality,
                CURRENT_TIMESTAMP as created_at
            FROM image_manifest i
            LEFT JOIN note_manifest n ON i.encounter_id = n.encounter_id
            LEFT JOIN vitals_manifest v ON i.encounter_id = v.encounter_id
        """)
    
    def get_contract_violations(self) -> Dict[str, Any]:
        """Get contract violation statistics"""
        violations = self.validator.get_violations()
        return {
            'total_violations': len(violations),
            'violations_by_type': {},
            'violations': violations
        }
    
    def close(self):
        """Close database connection"""
        self.conn.close()

def run_raw_ingestion_pipeline(images_dir: str, notes_dir: str, vitals_dir: str) -> Dict[str, Any]:
    """Run the complete raw data ingestion pipeline"""
    pipeline = RawDataIngestionPipeline()
    
    print("Starting raw data ingestion...")
    
    # Ingest images
    print("Ingesting images...")
    image_records = pipeline.ingest_images(images_dir)
    print(f"Processed {len(image_records)} images")
    
    # Ingest notes
    print("Ingesting clinical notes...")
    note_records = pipeline.ingest_notes(notes_dir)
    print(f"Processed {len(note_records)} notes")
    
    # Ingest vitals
    print("Ingesting vital signs...")
    vitals_records = pipeline.ingest_vitals(vitals_dir)
    print(f"Processed {len(vitals_records)} vitals")
    
    # Create curated manifest
    print("Creating curated manifest...")
    pipeline.create_curated_manifest()
    
    # Get violation stats
    violations = pipeline.get_contract_violations()
    print(f"Contract violations: {violations['total_violations']}")
    
    pipeline.close()
    
    return {
        'image_records': len(image_records),
        'note_records': len(note_records),
        'vitals_records': len(vitals_records),
        'violations': violations
    }
