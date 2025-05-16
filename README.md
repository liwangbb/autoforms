# 🧠 PDF Medical Form Pipeline CLI

## Overview

This CLI tool provides a comprehensive pipeline for processing medical PDF forms, including:

- Extracting form structure and user-fillable elements
- Generating structured questions from form content
- Summarizing EMR (Electronic Medical Record) documents
- Generating context-aware answers from the summary
- Estimating answer box locations (only for image based PDFs)
- Visualizing form-question-answer layout (only for image based PDFs)
- Filling back the answers into the original PDF

Image-based PDFs (scanned or handwritten) are parsed using **Google Document AI** and do **not** require embedded AcroForm fields.

---

## Project Structure and Workflow

```plaintext
autosribe_forms
│
├── form_pipeline_api.py -----------> (Entry Point for API: Exposes `/run-pipeline/` endpoint to process PDFs + EMRs via FastAPI)
│
├── main.py  -----------------------> (Entry Point for CLI: Parses arguments, detects PDF type, selects & runs pipeline)
│
├── services/  ---------------------> (Core processing logic)
│   │
│   ├── config/ --------------------> (Configuration files)
│   │   ├── google_config.py ------> (Google Cloud/Document AI credentials & endpoints)
│   │   └── openai_config.py ------> (Azure OpenAI credentials & deployment info)
│   │
│   ├── pipeline/ ------------------> (Orchestrates the workflow steps)
│   │   ├── form_processor_base.py -> (Abstract base class for pipelines)
│   │   ├── digital_form_processor.py (Handles workflow for Digital PDFs)
│   │   └── image_form_processor.py -> (Handles workflow for Image PDFs)
│   │
│   ├── digital_pdf/ ---------------> (Modules specific to Digital PDF processing)
│   │   ├── extractor.py ----------> (1. Extracts text & form fields from digital PDF)
│   │   ├── scorer.py -------------> (Helper for extractor: Matches fields to pages)
│   │   ├── question_generator.py -> (2. Generates questions from extracted fields)
│   │   └── answer_filler.py ------> (5. Fills answers into digital PDF AcroForms)
│   │
│   ├── image_pdf/ -----------------> (Modules specific to Image PDF processing)
│   │   ├── pdf_parser.py ---------> (1a. Extracts text segments & boxe)
│   │   ├── pdf_block_combiner.py -> (1b. Combines segments into logical blocks)
│   │   ├── question_extractor.py -> (2. Extracts questions from text blocks)
│   │   ├── question_matcher.py ---> (3. Matches generated questions to text blocks)
│   │   ├── adaptive_analyzer.py --> (4. Estimates answer box locations based on layout)
│   │   └── image_pdf_filler.py ---> (7. Fills answers by drawing text onto PDF images)
│   │
│   ├── answer_generator.py --------> (COMMON: Generates answers from EMR summary & questions)
│   └── summarize_data.py ----------> (COMMON: Summarizes EMR text files via OpenAI)
│
├── utils/ -------------------------> (Helper utilities)
│   │
│   ├── azure_openai_helper.py -----> (Handles Azure OpenAI client setup & API calls)
│   ├── docai_client.py ------------> (Handles Google Document AI client setup & API calls)
│   └── pdf_helper.py --------------> (Detects PDF type, visualizes image layout, packages output)
│
├── input/ -------------------------> (Example input files)
│   ├── emr/
│   │   ├── digital/ (...)
│   │   └── image/ (...)
│   └── form/ (...)
│
├── outputs/ -----------------------> (Default location for generated results)
│
├── .env ---------------------------> (Stores API keys and endpoints - *Not uploaded, but referenced*)
├── README.md ----------------------> (Project documentation)
└── requirements.txt ---------------> (Python package dependencies)
```
---

## 🧰 Prerequisites

- Python 3.8+
- Azure OpenAI access (for question & answer generation)
- Google Cloud Document AI access (for image-based PDF parsing)
- `pdftk` installed (for digital form filling fallback)

---

## 🔧 Environment Setup

Create a `.env` file at the project root with the following keys:

```env
# Azure OpenAI (GPT-4) configuration
AZURE_OPENAI_GPT4_DEPLOYMENT=your_deployment_name
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_LOCATION=your-region
AZURE_OPENAI_API_KEY=your_api_key
OPENAI_API_VERSION=2023-07-01-preview

# Google Document AI configuration
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account.json
DOCUMENT_AI_SCOPES=https://www.googleapis.com/auth/cloud-platform
DOCUMENT_AI_ENDPOINT=https://us-documentai.googleapis.com
```

---

## 🐍 Python Setup

### Using `venv`

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install pdftk
```

If pdftk isn't available via pip on your platform, install it via brew (brew install pdftk-java) or apt (sudo apt install pdftk)

### OR using `conda`

```bash
conda create -n medical-pdf-pipeline python=3.8
conda activate medical-pdf-pipeline
pip install -r requirements.txt
pip install pdftk
```

### OR using `pipenv`

```bash
pip install pipenv
pipenv install
pipenv shell
```

---

## 🧪 Pre-Commit Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## 🚀 Usage

### Full Pipeline (Digital or Image PDF)

```bash
python main.py <input_pdf_path> --emr <emr_file1.txt> [<emr_file2.txt>...] -o <output_dir> [-v]
```

### Flags

| Flag             | Description                          |
|------------------|--------------------------------------|
| `-i, --input`    | Path to input PDF                    |
| `--emr`          | List of `.txt` files for EMR input   |
| `-o, --output`   | Output folder (auto-created)         |
| `-v, --visualize`| (Optional) Output image visualizations |

---

## 📦 Output Files

| File                | Description                                                             |
|---------------------|-------------------------------------------------------------------------|
| `final_blocks.json` | Form structure + linked questions + answer boxes + answers              |
| `answers.json`      | Answers with associated question keys                                   |
| `summary.txt`       | EMR summary text used to generate answers                               |
| `filled_form.pdf`   | Final filled PDF (only for digital PDFs)                                |
| `form_analysis_*.png`| Optional visualization of each page's layout                           |
| `fill_stats.json`   | Fill diagnostics (number of fields filled, skipped, errors)             |

---

## ✅ Example

```bash
python3 main.py input/form/canadalife.pdf --emr input/emr/image/emr_image_test_clinical_info.txt -v
```

This is a cleaned, public version of a private project I contributed to while working at Mutuo.

Note:
- No proprietary code or data is included.
- All logic here was written or refactored by me.
- Original repo remains private per company policy.

This version is for **portfolio and skill demonstration purposes only.**
