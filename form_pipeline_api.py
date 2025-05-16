# autosribe_forms/api/api.py

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pathlib import Path
from datetime import datetime
import shutil

from services.pipeline.digital_form_processor import DigitalFormProcessor
from services.pipeline.image_form_processor import ImageFormProcessor
from utils.pdf_helper import is_digital_form_pdf

app = FastAPI(title="Autoscribe PDF Form Processor API")

@app.post("/run-pipeline/")
async def run_pipeline(
    input_pdf: UploadFile = File(...),
    emr_files: list[UploadFile] = File(...),
    visualize: bool = Form(False)
):
    try:
        output_dir = Path(f"outputs/api-run-{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save input file
        input_pdf_path = output_dir / input_pdf.filename
        with input_pdf_path.open("wb") as f:
            shutil.copyfileobj(input_pdf.file, f)

        # Save EMR files
        emr_paths = []
        for file in emr_files:
            emr_path = output_dir / file.filename
            with emr_path.open("wb") as f:
                shutil.copyfileobj(file.file, f)
            emr_paths.append(str(emr_path))

        # Detect PDF type and run pipeline
        if is_digital_form_pdf(str(input_pdf_path)):
            processor = DigitalFormProcessor(str(input_pdf_path), emr_paths, output_dir)
        else:
            processor = ImageFormProcessor(str(input_pdf_path), emr_paths, output_dir)

        processor.run_pipeline(visualize_output=visualize)

        return JSONResponse({"status": "success", "output_dir": str(output_dir)})

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
