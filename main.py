#!/usr/bin/env python3
"""
Granite Lite - Semantic Layer for ChestMNIST
Main application entry point
"""

import os
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from raw_ingestion import run_raw_ingestion_pipeline
from semantic_api import app

def ingest_data():
    """Ingest raw data files into the semantic layer"""
    print("Starting Granite Lite data ingestion...")
    
    # Create necessary directories
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    # Copy images to static directory for web access
    import shutil
    static_images_dir = "static/images"
    os.makedirs(static_images_dir, exist_ok=True)
    
    # Copy images from data/raw/images to static/images
    source_dir = "data/raw/images"
    if os.path.exists(source_dir):
        for filename in os.listdir(source_dir):
            if filename.endswith('.png'):
                shutil.copy2(
                    os.path.join(source_dir, filename),
                    os.path.join(static_images_dir, filename)
                )
        print(f"Copied images to {static_images_dir}")
    
    # Run raw data ingestion pipeline
    print("Ingesting raw data files...")
    results = run_raw_ingestion_pipeline(
        images_dir="data/raw/images",
        notes_dir="data/raw/notes", 
        vitals_dir="data/raw/vitals"
    )
    
    print("\nIngestion Results:")
    print(f"- Images processed: {results['image_records']}")
    print(f"- Notes processed: {results['note_records']}")
    print(f"- Vitals processed: {results['vitals_records']}")
    print(f"- Contract violations: {results['violations']['total_violations']}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Granite Lite Semantic Layer")
    parser.add_argument("--ingest", action="store_true", help="Ingest raw data files")
    parser.add_argument("--server", action="store_true", help="Start the semantic API server")
    parser.add_argument("--port", type=int, default=8000, help="Port for the API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host for the API server")
    
    args = parser.parse_args()
    
    if args.ingest:
        ingest_data()
    elif args.server:
        import uvicorn
        print(f"Starting Granite Lite API server on {args.host}:{args.port}")
        print("Available endpoints:")
        print(f"  - API: http://{args.host}:{args.port}")
        print(f"  - Reviewer UI: http://{args.host}:{args.port}/reviewer/enc_00001")
        print(f"  - Health check: http://{args.host}:{args.port}/health")
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
