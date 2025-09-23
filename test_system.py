#!/usr/bin/env python3
"""
Test script for Granite Lite semantic layer
Demonstrates all functionality
"""

import sys
import os
sys.path.append('src')

from semantic_api import SemanticFusionEngine
import json

def test_system():
    """Test the complete granite-lite system"""
    print("=== Granite Lite System Test ===\n")
    
    # Initialize fusion engine
    engine = SemanticFusionEngine('data/processed/granite_lite.db')
    
    # 1. List all encounters
    print("1. Available Encounters:")
    encounters = engine.conn.execute("""
        SELECT encounter_id, created_at 
        FROM curated_manifest 
        ORDER BY encounter_id 
        LIMIT 10
    """).fetchall()
    
    for row in encounters:
        print(f"   - {row[0]} (created: {row[1]})")
    
    # 2. Test event fusion for different encounters
    print("\n2. Event Fusion Examples:")
    test_encounters = ['enc_00001', 'enc_00006', 'enc_00007', 'enc_00012']
    
    for encounter_id in test_encounters:
        try:
            event = engine.fuse_event(encounter_id)
            print(f"\n   Encounter: {encounter_id}")
            print(f"   Diagnosis: {event.diagnosis}")
            print(f"   Confidence: {event.confidence:.2f}")
            print(f"   Evidence sources: {len(event.evidence)}")
            
            # Show evidence details
            for evidence in event.evidence:
                if evidence['modality'] == 'image':
                    print(f"     - Image: {evidence['findings']}")
                elif evidence['modality'] == 'note':
                    print(f"     - Note: {evidence['content'][:60]}...")
                elif evidence['modality'] == 'vitals':
                    summary = evidence['summary']
                    print(f"     - Vitals: HR={summary['avg_hr']:.1f}, SpO2={summary['avg_spo2']:.1f}, RR={summary['avg_rr']:.1f}")
                    
        except Exception as e:
            print(f"   Error for {encounter_id}: {e}")
    
    # 3. Test contract validation
    print("\n3. Contract Validation:")
    violations = engine.conn.execute("""
        SELECT COUNT(*) FROM image_manifest
    """).fetchone()[0]
    print(f"   Total image records: {violations}")
    
    violations = engine.conn.execute("""
        SELECT COUNT(*) FROM note_manifest
    """).fetchone()[0]
    print(f"   Total note records: {violations}")
    
    violations = engine.conn.execute("""
        SELECT COUNT(*) FROM vitals_manifest
    """).fetchone()[0]
    print(f"   Total vitals records: {violations}")
    
    # 4. Test correction submission
    print("\n4. Testing Correction Submission:")
    from semantic_api import CorrectionRequest
    correction = CorrectionRequest(
        encounter_id="enc_00001",
        diagnosis="pneumonia",
        confidence=0.9,
        corrections={"reason": "Clinical assessment", "notes": "Test correction"}
    )
    
    try:
        engine.save_correction(correction)
        print("   [SUCCESS] Correction saved successfully")
    except Exception as e:
        print(f"   [ERROR] Error saving correction: {e}")
    
    # 5. Show data lineage
    print("\n5. Data Lineage Example:")
    event = engine.fuse_event('enc_00006')
    print(f"   Encounter: {event.encounter_id}")
    print(f"   Lineage: {json.dumps(event.lineage, indent=2)}")
    
    engine.close()
    print("\n=== Test Complete ===")
    print("\nTo start the API server, run:")
    print("  python main.py --server")
    print("\nTo access the reviewer UI, visit:")
    print("  http://localhost:8000/reviewer/enc_00001")

if __name__ == "__main__":
    test_system()
