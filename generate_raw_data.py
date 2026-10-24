#!/usr/bin/env python3
"""
Generate raw data files for granite-lite pipeline
This creates the clinical notes and vital signs as raw data files
"""

import argparse
import os
import random
import sys
sys.path.append('src')

from data_generator import ClinicalNoteGenerator, VitalsGenerator
from models import parse_filename_to_encounter
import glob

def generate_raw_data(seed: int = 42):
    """Generate all raw data files"""
    print("Generating raw data files...")
    random.seed(seed)  # same notes and vital values on every run (timestamps still use the current time)
    
    # Create directories
    os.makedirs("data/raw/notes", exist_ok=True)
    os.makedirs("data/raw/vitals", exist_ok=True)
    
    # Initialize generators
    note_gen = ClinicalNoteGenerator()
    vitals_gen = VitalsGenerator()
    
    # Process each image file
    image_files = glob.glob("data/raw/images/*.png")
    processed_count = 0
    
    for image_file in sorted(image_files):
        filename = os.path.basename(image_file)
        try:
            # Parse filename to get encounter_id and labels
            encounter_id, label_vector = parse_filename_to_encounter(filename)
            
            # Generate clinical note
            note_content = note_gen.generate_note(label_vector, encounter_id)
            key_tokens = note_gen.extract_key_tokens(note_content)
            
            # Save note to file
            note_file = f"data/raw/notes/{encounter_id}_note.txt"
            with open(note_file, 'w') as f:
                f.write(note_content)
            
            # Generate vitals
            vitals_data = vitals_gen.generate_vitals(encounter_id)
            vitals_file = f"data/raw/vitals/{encounter_id}_vitals.csv"
            vitals_gen.save_vitals_csv(vitals_data, vitals_file)
            
            processed_count += 1
            if processed_count % 10 == 0:
                print(f"Processed {processed_count} encounters...")
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            continue
    
    print(f"Generated raw data for {processed_count} encounters")
    print("Raw data structure:")
    print("  data/raw/images/    - ChestMNIST images")
    print("  data/raw/notes/     - Clinical notes")
    print("  data/raw/vitals/    - Vital signs CSV files")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic notes and vitals for the ChestMNIST images")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    generate_raw_data(parser.parse_args().seed)
