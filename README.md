# Disaster Relief Agentic Assistant

## Overview
This project aims to develop an agentic system to help state and local government officials navigate the complex process of obtaining federal assistance after a natural disaster.

## Current Status
Currently, we're focusing on FEMA disaster declaration request forms (Form 010-0-13), of which we have a dataset of 100+. We're setting up a basic parsing pipeline to extract structured data from these forms, along with an eval pipeline to verify the accuracy of this parsing (using LLM-as-judge). Both rely on native PDF parsing from `gemini-2.0-flash`.

Initial results are promising with high overall parsing accuracy (90+%), though we've encountered some issues with checkbox detection and empty field handling that need improvement.

See the `experiments` subdirectory for detailed results and updates.

## Components
### Storage System
- `storage.py`: Manages document storage with UUID-based organization
- `generate_docetl.py`: Converts stored documents to DocETL-compatible JSON format
### Data Processing Pipeline
- Parse pipeline (`parse.yaml`): Extracts structured data from PDFs page-by-page
- Evaluation pipeline (`check.yaml`): Verifies extraction accuracy
