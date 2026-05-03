# Multimodal AI Semantic Layer for ChestMNIST

Granite Lite -a minimal, production-lean semantic layer that fuses three modalities (image, text, time-series) for clinical encounters using the ChestMNIST dataset.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Ingest Raw Data
```bash
python main.py --ingest
```

### 3. Start API Server
```bash
python main.py --server
```

### 4. Access the System
- **API**: http://localhost:8000
- **Reviewer UI**: http://localhost:8000/reviewer/enc_00001
- **API Docs**: http://localhost:8000/docs

## What It Does

### Multi-Modal Fusion
- **Images**: Chest X-ray images with diagnostic labels
- **Text**: Clinical notes with medical terminology
- **Time-series**: Vital signs monitoring data

### Semantic API
- `GET /event/{encounter_id}` - Get fused clinical event
- `GET /encounters` - List all encounters
- `POST /corrections` - Submit human corrections
- `GET /reviewer/{encounter_id}` - Web-based reviewer interface

### Data Quality
- Contract validation for all data records
- Quality scoring per modality
- Evidence tracking with confidence metrics
- Human-in-the-loop correction system

## Example Usage

### Get a Clinical Event
```bash
curl http://localhost:8000/event/enc_00006
```

### Submit a Correction
```bash
curl -X POST http://localhost:8000/corrections \
  -H "Content-Type: application/json" \
  -d '{"encounter_id": "enc_00001", "diagnosis": "pneumonia", "confidence": 0.9, "corrections": {"reason": "Clinical assessment"}}'
```

## Data Structure

### Raw Data
```
data/raw/
├── images/           # ChestMNIST images (50 PNG files)
├── notes/            # Clinical notes (50 TXT files)
└── vitals/           # Vital signs (50 CSV files)
```

### Database
- **DuckDB** with 4 manifest tables
- **Contract validation** for data quality
- **Unified curated_manifest** for cross-modal queries

## Medical Conditions

The system recognizes 14 ChestMNIST conditions:
- atelectasis, cardiomegaly, effusion, infiltration
- mass, nodule, pneumonia, pneumothorax
- consolidation, edema, emphysema, fibrosis
- pleural, hernia

## Architecture

- **FastAPI** for RESTful API
- **DuckDB** for analytical database
- **Contract validation** for data quality
- **Multi-modal fusion** for evidence gathering
- **Web UI** for human review and correction

## Development

### Project Structure
```
granite-lite/
├── src/                    # Source code
├── data/raw/              # Raw data files
├── data/processed/        # Generated data & database
├── static/                # Web assets
├── templates/             # HTML templates
├── main.py               # Entry point
└── requirements.txt      # Dependencies
```

### Key Files
- `main.py` - Application entry point
- `src/raw_ingestion.py` - Data ingestion pipeline
- `src/semantic_api.py` - FastAPI application
- `src/models.py` - Data models and validation

## Dataset Acknowledgement

This project uses the ChestMNIST dataset from [MedMNIST](https://medmnist.com/). We acknowledge the original authors for providing this valuable medical imaging dataset for research and development purposes.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Copyright

Copyright (c) 2025
Data Engineering for Multimodal AI

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
