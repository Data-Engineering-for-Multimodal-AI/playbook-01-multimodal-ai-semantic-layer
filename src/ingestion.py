"""
Data ingestion pipeline with contract validation
"""

import os
import glob
from datetime import datetime
from typing import List, Dict, Any
import duckdb

from models import (
    ImageRecord, NoteRecord, VitalsRecord, 
    ContractValidator, parse_filename_to_encounter
)
from data_generator import generate_synthetic_data_for_encounter

class DataIngestionPipeline:
    """Handles data ingestion with contract validation"""
    
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
    
    def ingest_synthetic_data(self, encounters: List[str], output_dir: str) -> Dict[str, Any]:
        """Generate and ingest synthetic clinical notes and vitals"""
        note_records = []
        vitals_records = []
        
        for encounter_id in encounters:
            # Get label vector from image manifest
            result = self.conn.execute("""
                SELECT label_vector FROM image_manifest 
                WHERE encounter_id = ?
            """, [encounter_id]).fetchone()
            
            if not result:
                continue
                
            label_vector = eval(result[0])  # Convert string back to list
            
            # Generate synthetic data
            synthetic_data = generate_synthetic_data_for_encounter(
                encounter_id, label_vector, output_dir
            )
            
            # Create note record
            note_record = NoteRecord(
                entity_id=f"entity_{encounter_id}",
                encounter_id=encounter_id,
                modality="note",
                timestamp=datetime.now(),
                provenance="synthetic_generator",
                quality=0.85,  # Synthetic data quality
                content=synthetic_data['note_content'],
                key_tokens=synthetic_data['key_tokens']
            )
            
            if self.validator.validate_record(note_record):
                note_records.append(note_record)
                self._insert_note_record(note_record)
            
            # Create vitals record
            vitals_record = VitalsRecord(
                entity_id=f"entity_{encounter_id}",
                encounter_id=encounter_id,
                modality="vitals",
                timestamp=datetime.now(),
                provenance="synthetic_generator",
                quality=0.90,  # Synthetic vitals quality
                vitals_data=synthetic_data['vitals_data']
            )
            
            if self.validator.validate_record(vitals_record):
                vitals_records.append(vitals_record)
                self._insert_vitals_record(vitals_record, synthetic_data['vitals_file'])
        
        return {
            'note_records': note_records,
            'vitals_records': vitals_records
        }
    
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

def run_ingestion_pipeline(images_dir: str, output_dir: str) -> Dict[str, Any]:
    """Run the complete ingestion pipeline"""
    pipeline = DataIngestionPipeline()
    
    print("Starting data ingestion...")
    
    # Ingest images
    print("Ingesting images...")
    image_records = pipeline.ingest_images(images_dir)
    print(f"Processed {len(image_records)} images")
    
    # Get encounter IDs
    encounters = [record.encounter_id for record in image_records]
    
    # Generate and ingest synthetic data
    print("Generating synthetic clinical notes and vitals...")
    synthetic_data = pipeline.ingest_synthetic_data(encounters, output_dir)
    print(f"Generated {len(synthetic_data['note_records'])} notes")
    print(f"Generated {len(synthetic_data['vitals_records'])} vitals")
    
    # Create curated manifest
    print("Creating curated manifest...")
    pipeline.create_curated_manifest()
    
    # Get violation stats
    violations = pipeline.get_contract_violations()
    print(f"Contract violations: {violations['total_violations']}")
    
    pipeline.close()
    
    return {
        'image_records': len(image_records),
        'note_records': len(synthetic_data['note_records']),
        'vitals_records': len(synthetic_data['vitals_records']),
        'violations': violations
    }
