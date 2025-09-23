#!/usr/bin/env python3
"""
Demo script for Granite Lite - shows the complete system in action
"""

import requests
import json
import time
import subprocess
import sys
import os

def start_server():
    """Start the API server in the background"""
    print("Starting Granite Lite API server...")
    process = subprocess.Popen([
        sys.executable, "main.py", "--server", "--port", "8000"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    time.sleep(3)
    return process

def test_api_endpoints():
    """Test all API endpoints"""
    base_url = "http://localhost:8000"
    
    print("\n=== Testing API Endpoints ===\n")
    
    # 1. Health check
    print("1. Health Check:")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 2. List encounters
    print("\n2. List Encounters:")
    try:
        response = requests.get(f"{base_url}/encounters", timeout=5)
        encounters = response.json()
        print(f"   Found {len(encounters)} encounters")
        for enc in encounters[:5]:  # Show first 5
            print(f"   - {enc['encounter_id']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 3. Get specific event
    print("\n3. Get Event (enc_00006):")
    try:
        response = requests.get(f"{base_url}/event/enc_00006", timeout=5)
        event = response.json()
        print(f"   Diagnosis: {event['diagnosis']}")
        print(f"   Confidence: {event['confidence']:.2f}")
        print(f"   Evidence sources: {len(event['evidence'])}")
        
        for evidence in event['evidence']:
            if evidence['modality'] == 'image':
                print(f"     - Image findings: {evidence['findings']}")
            elif evidence['modality'] == 'note':
                print(f"     - Note: {evidence['content'][:50]}...")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 4. Submit correction
    print("\n4. Submit Correction:")
    try:
        correction = {
            "encounter_id": "enc_00006",
            "diagnosis": "pneumonia",
            "confidence": 0.9,
            "corrections": {
                "reason": "Clinical assessment",
                "notes": "Patient shows signs of pneumonia"
            }
        }
        response = requests.post(
            f"{base_url}/corrections", 
            json=correction, 
            timeout=5
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")

def main():
    """Run the complete demo"""
    print("=== Granite Lite Demo ===\n")
    
    # Check if data is set up
    if not os.path.exists("data/processed/granite_lite.db"):
        print("Setting up data first...")
        subprocess.run([sys.executable, "main.py", "--setup"], check=True)
        print("Data setup complete!\n")
    
    # Start server
    server_process = start_server()
    
    try:
        # Test API
        test_api_endpoints()
        
        print("\n=== Demo Complete ===")
        print("\nThe system is now running! You can:")
        print("1. Visit http://localhost:8000/reviewer/enc_00006 for the reviewer UI")
        print("2. Use the API endpoints directly")
        print("3. Check the database for corrections")
        
        print("\nPress Ctrl+C to stop the server...")
        
        # Keep server running
        server_process.wait()
        
    except KeyboardInterrupt:
        print("\nStopping server...")
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")

if __name__ == "__main__":
    main()
