"""
Semantic API for event fusion and evidence/lineage tracking

Copyright (c) 2025
Data Engineering for Multimodal AI

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import duckdb
import json
from datetime import datetime
import os

from models import FusedEvent

app = FastAPI(title="Granite Lite Semantic API", version="1.0.0")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Database connection
DB_PATH = "data/processed/granite_lite.db"

class CorrectionRequest(BaseModel):
    encounter_id: str
    diagnosis: str
    confidence: float
    corrections: Dict[str, Any]

class EventResponse(BaseModel):
    encounter_id: str
    diagnosis: str
    confidence: float
    evidence: List[Dict[str, Any]]
    lineage: Dict[str, Any]
    timestamp: str

class SemanticFusionEngine:
    """Handles event fusion and evidence gathering"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = duckdb.connect(db_path)
        
        # Medical condition mapping
        self.condition_names = {
            0: 'atelectasis', 1: 'cardiomegaly', 2: 'effusion', 3: 'infiltration',
            4: 'mass', 5: 'nodule', 6: 'pneumonia', 7: 'pneumothorax',
            8: 'consolidation', 9: 'edema', 10: 'emphysema', 11: 'fibrosis',
            12: 'pleural', 13: 'hernia'
        }
    
    def get_encounter_data(self, encounter_id: str) -> Optional[Dict[str, Any]]:
        """Get all data for a specific encounter"""
        result = self.conn.execute("""
            SELECT 
                encounter_id, entity_id, image_path, note_content, vitals_path,
                image_quality, note_quality, vitals_quality, created_at
            FROM curated_manifest 
            WHERE encounter_id = ?
        """, [encounter_id]).fetchone()
        
        if not result:
            return None
        
        return {
            'encounter_id': result[0],
            'entity_id': result[1],
            'image_path': result[2],
            'note_content': result[3],
            'vitals_path': result[4],
            'image_quality': result[5],
            'note_quality': result[6],
            'vitals_quality': result[7],
            'created_at': result[8]
        }
    
    def get_image_labels(self, encounter_id: str) -> List[int]:
        """Get image label vector for encounter"""
        result = self.conn.execute("""
            SELECT label_vector FROM image_manifest 
            WHERE encounter_id = ?
        """, [encounter_id]).fetchone()
        
        if result:
            return eval(result[0])  # Convert string back to list
        return []
    
    def get_vitals_summary(self, vitals_path: str) -> Dict[str, Any]:
        """Get summary statistics from vitals data"""
        if not os.path.exists(vitals_path):
            return {}
        
        # Read vitals CSV and compute summary stats
        vitals_df = self.conn.execute(f"""
            SELECT * FROM read_csv_auto('{vitals_path}')
        """).df()
        
        if vitals_df.empty:
            return {}
        
        return {
            'avg_hr': float(vitals_df['hr'].mean()),
            'avg_spo2': float(vitals_df['spo2'].mean()),
            'avg_rr': float(vitals_df['rr'].mean()),
            'min_spo2': float(vitals_df['spo2'].min()),
            'max_hr': float(vitals_df['hr'].max()),
            'data_points': len(vitals_df)
        }
    
    def fuse_event(self, encounter_id: str) -> FusedEvent:
        """Fuse all modalities into a single event with evidence and lineage"""
        encounter_data = self.get_encounter_data(encounter_id)
        if not encounter_data:
            raise ValueError(f"Encounter {encounter_id} not found")
        
        # Get image labels
        label_vector = self.get_image_labels(encounter_id)
        
        # Determine primary diagnosis based on image labels
        active_conditions = [i for i, has_condition in enumerate(label_vector) if has_condition]
        
        if active_conditions:
            primary_condition_idx = active_conditions[0]  # Take first active condition
            diagnosis = self.condition_names[primary_condition_idx]
            confidence = 0.8  # Base confidence for image-based diagnosis
        else:
            diagnosis = "No acute findings"
            confidence = 0.6
        
        # Gather evidence from all modalities
        evidence = []
        
        # Image evidence
        if label_vector:
            image_evidence = {
                'modality': 'image',
                'source': encounter_data['image_path'],
                'quality': encounter_data['image_quality'],
                'findings': [self.condition_names[i] for i in active_conditions],
                'confidence': encounter_data['image_quality'] * 0.9
            }
            evidence.append(image_evidence)
        
        # Note evidence
        if encounter_data['note_content']:
            note_evidence = {
                'modality': 'note',
                'source': 'clinical_note',
                'quality': encounter_data['note_quality'],
                'content': encounter_data['note_content'],
                'confidence': encounter_data['note_quality'] * 0.7
            }
            evidence.append(note_evidence)
        
        # Vitals evidence
        vitals_summary = self.get_vitals_summary(encounter_data['vitals_path'])
        if vitals_summary:
            vitals_evidence = {
                'modality': 'vitals',
                'source': encounter_data['vitals_path'],
                'quality': encounter_data['vitals_quality'],
                'summary': vitals_summary,
                'confidence': encounter_data['vitals_quality'] * 0.6
            }
            evidence.append(vitals_evidence)
        
        # Calculate overall confidence
        if evidence:
            overall_confidence = sum(e['confidence'] for e in evidence) / len(evidence)
        else:
            overall_confidence = 0.5
        
        # Create lineage
        lineage = {
            'data_sources': [e['source'] for e in evidence],
            'processing_timestamp': datetime.now().isoformat(),
            'fusion_algorithm': 'weighted_evidence',
            'quality_scores': {
                'image': encounter_data['image_quality'],
                'note': encounter_data['note_quality'],
                'vitals': encounter_data['vitals_quality']
            }
        }
        
        return FusedEvent(
            encounter_id=encounter_id,
            diagnosis=diagnosis,
            confidence=overall_confidence,
            evidence=evidence,
            lineage=lineage,
            timestamp=datetime.now()
        )
    
    def save_correction(self, correction: CorrectionRequest):
        """Save human correction to database"""
        # Create corrections table if it doesn't exist
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS corrections (
                encounter_id VARCHAR,
                original_diagnosis VARCHAR,
                corrected_diagnosis VARCHAR,
                confidence FLOAT,
                corrections JSON,
                corrected_at TIMESTAMP,
                corrected_by VARCHAR
            )
        """)
        
        # Insert correction
        self.conn.execute("""
            INSERT INTO corrections 
            (encounter_id, original_diagnosis, corrected_diagnosis, confidence, corrections, corrected_at, corrected_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            correction.encounter_id,
            "auto_generated",  # We'd get this from the original event
            correction.diagnosis,
            correction.confidence,
            json.dumps(correction.corrections),
            datetime.now(),
            "human_reviewer"
        ))
    
    def close(self):
        """Close database connection"""
        self.conn.close()

# Initialize fusion engine
fusion_engine = SemanticFusionEngine(DB_PATH)

@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {"message": "Granite Lite Semantic API", "version": "1.0.0"}

@app.get("/event/{encounter_id}", response_model=EventResponse)
async def get_event(encounter_id: str):
    """Get fused event for a specific encounter"""
    try:
        event = fusion_engine.fuse_event(encounter_id)
        
        return EventResponse(
            encounter_id=event.encounter_id,
            diagnosis=event.diagnosis,
            confidence=event.confidence,
            evidence=event.evidence,
            lineage=event.lineage,
            timestamp=event.timestamp.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/encounters")
async def list_encounters():
    """List all available encounters"""
    result = fusion_engine.conn.execute("""
        SELECT encounter_id, created_at FROM curated_manifest 
        ORDER BY encounter_id
    """).fetchall()
    
    return [{"encounter_id": row[0], "created_at": row[1]} for row in result]

@app.post("/corrections")
async def submit_correction(correction: CorrectionRequest):
    """Submit a human correction"""
    try:
        fusion_engine.save_correction(correction)
        return {"message": "Correction saved successfully", "encounter_id": correction.encounter_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save correction: {str(e)}")

@app.get("/reviewer/{encounter_id}", response_class=HTMLResponse)
async def reviewer_ui(encounter_id: str):
    """Simple reviewer UI for human-in-the-loop correction"""
    try:
        event = fusion_engine.fuse_event(encounter_id)
        
        # Get all encounters for navigation
        encounters = fusion_engine.conn.execute("""
            SELECT encounter_id FROM curated_manifest ORDER BY encounter_id
        """).fetchall()
        
        return templates.TemplateResponse("reviewer.html", {
            "request": {"url": {"pathname": f"/reviewer/{encounter_id}"}},
            "encounter_id": encounter_id,
            "event": event,
            "encounters": [row[0] for row in encounters]
        })
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
