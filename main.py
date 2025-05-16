import argparse
from datetime import datetime
from pathlib import Path

from services.pipeline.digital_form_processor import DigitalFormProcessor
from services.pipeline.image_form_processor import ImageFormProcessor
from utils.pdf_helper import is_digital_form_pdf


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="🧠 PDF Medical Form Pipeline CLI"
    )

    parser.add_argument("input", help="Path to input PDF file")
    parser.add_argument(
        "--emr", nargs="+", required=True, help="Paths to EMR document files"
    )
    parser.add_argument("-o", "--output", help="Output directory (optional)")
    parser.add_argument(
        "-v", "--visualize", action="store_true", help="Generate visual output"
    )

    return parser.parse_args()


def setup_output_directory(args):
    return (
        Path(args.output)
        if args.output
        else Path(f"outputs/run-{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    )


def run_all_pipeline(
    pdf_path: str,
    emr_files: list[str],
    output_dir: Path,
    visualize_output: bool,
):
    print("🔍 Detecting PDF type...")
    if is_digital_form_pdf(pdf_path):
        print("📄 Detected: Digital fillable PDF form")
        processor = DigitalFormProcessor(pdf_path, emr_files, output_dir)
    else:
        print("🖼️ Detected: Image-based scanned PDF form")
        processor = ImageFormProcessor(pdf_path, emr_files, output_dir)

    processor.run_pipeline(visualize_output=visualize_output)


def main():
    args = parse_arguments()
    input_pdf = args.input
    emr_files = args.emr
    output_dir = setup_output_directory(args)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_all_pipeline(
        input_pdf, emr_files, output_dir, visualize_output=args.visualize
    )


if __name__ == "__main__":
    main()
