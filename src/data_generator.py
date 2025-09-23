"""
Synthetic data generation for clinical notes and vitals
"""

import random
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Any
import os

class ClinicalNoteGenerator:
    """Generates synthetic clinical notes with medical terminology"""
    
    def __init__(self):
        self.base_templates = [
            "Patient presents with {symptom}. Physical examination reveals {finding}. {assessment}",
            "Chief complaint: {symptom}. On examination, {finding}. Clinical impression: {assessment}",
            "History of {symptom}. Examination shows {finding}. {assessment}",
            "Patient reports {symptom}. Physical findings include {finding}. {assessment}"
        ]
        
        self.symptoms = [
            "chest pain", "shortness of breath", "cough", "fever", "fatigue",
            "respiratory distress", "chest tightness", "wheezing"
        ]
        
        self.findings = [
            "bilateral lung fields clear", "mild respiratory distress", 
            "normal heart sounds", "no acute distress", "stable vital signs",
            "decreased breath sounds", "crackles heard", "wheezing present"
        ]
        
        self.clinical_terms = [
            "opacity", "consolidation", "infiltrate", "pneumonia", "atelectasis",
            "cardiomegaly", "effusion", "mass", "nodule", "pneumothorax",
            "edema", "emphysema", "fibrosis", "pleural", "hernia"
        ]
        
        self.assessments = [
            "Continue current treatment plan", "Monitor closely", 
            "Consider additional imaging", "Follow up in 1 week",
            "No acute intervention needed", "Stable condition"
        ]
    
    def generate_note(self, label_vector: List[int], encounter_id: str) -> str:
        """Generate a clinical note based on the label vector"""
        template = random.choice(self.base_templates)
        symptom = random.choice(self.symptoms)
        finding = random.choice(self.findings)
        assessment = random.choice(self.assessments)
        
        # Add clinical terms with ~30% probability
        clinical_terms = []
        for i, has_condition in enumerate(label_vector):
            if has_condition and random.random() < 0.3:
                clinical_terms.append(self.clinical_terms[i])
        
        # Add clinical terms to the note
        if clinical_terms:
            finding += f". Notable findings include {', '.join(clinical_terms[:3])}"
        
        note = template.format(
            symptom=symptom,
            finding=finding,
            assessment=assessment
        )
        
        return note
    
    def extract_key_tokens(self, note: str) -> List[str]:
        """Extract clinical key tokens from the note"""
        tokens = []
        for term in self.clinical_terms:
            if term.lower() in note.lower():
                tokens.append(term)
        return tokens

class VitalsGenerator:
    """Generates synthetic vital signs time series data"""
    
    def __init__(self):
        self.baseline_vitals = {
            'hr': 75,      # heart rate
            'spo2': 98,    # oxygen saturation
            'rr': 16       # respiratory rate
        }
        
        self.variability = {
            'hr': 10,      # +/-10 bpm
            'spo2': 2,     # +/-2%
            'rr': 3        # +/-3 breaths/min
        }
    
    def generate_vitals(self, encounter_id: str, duration_minutes: int = 2) -> List[Dict[str, Any]]:
        """Generate 2-minute vitals at 1Hz (120 data points)"""
        vitals_data = []
        start_time = datetime.now()
        
        for i in range(duration_minutes * 60):  # 120 seconds
            timestamp = start_time + timedelta(seconds=i)
            
            # Generate realistic vital signs with some variation
            hr = max(60, min(120, self.baseline_vitals['hr'] + random.randint(-self.variability['hr'], self.variability['hr'])))
            spo2 = max(95, min(100, self.baseline_vitals['spo2'] + random.randint(-self.variability['spo2'], self.variability['spo2'])))
            rr = max(12, min(20, self.baseline_vitals['rr'] + random.randint(-self.variability['rr'], self.variability['rr'])))
            
            vitals_data.append({
                'ts': timestamp.isoformat(),
                'hr': hr,
                'spo2': spo2,
                'rr': rr
            })
        
        return vitals_data
    
    def save_vitals_csv(self, vitals_data: List[Dict[str, Any]], file_path: str):
        """Save vitals data to CSV file"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', newline='') as csvfile:
            fieldnames = ['ts', 'hr', 'spo2', 'rr']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(vitals_data)

def generate_synthetic_data_for_encounter(encounter_id: str, label_vector: List[int], output_dir: str):
    """Generate all synthetic data for a single encounter"""
    note_gen = ClinicalNoteGenerator()
    vitals_gen = VitalsGenerator()
    
    # Generate clinical note
    note_content = note_gen.generate_note(label_vector, encounter_id)
    key_tokens = note_gen.extract_key_tokens(note_content)
    
    # Generate vitals
    vitals_data = vitals_gen.generate_vitals(encounter_id)
    vitals_file = os.path.join(output_dir, f"{encounter_id}_vitals.csv")
    vitals_gen.save_vitals_csv(vitals_data, vitals_file)
    
    return {
        'note_content': note_content,
        'key_tokens': key_tokens,
        'vitals_data': vitals_data,
        'vitals_file': vitals_file
    }
