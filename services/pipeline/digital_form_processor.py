import json
import time
from pathlib import Path
from typing import Any, Dict, List

from services.answer_generator import QuestionAnswerGenerator
from services.digital_pdf.answer_filler import DigitalPDFFiller
from services.digital_pdf.extractor import PDFExtractor
from services.digital_pdf.question_generator import QuestionGenerator
from services.pipeline.form_processor_base import BaseFormProcessor
from services.summarize_data import DocumentSummarizer
from utils.pdf_helper import package_pipeline_output


class DigitalFormProcessor(BaseFormProcessor):
    def extract_form_elements(self) -> List[Dict[str, Any]]:
        print("🔍 Step 1: Extracting form elements from digital PDF...")
        start = time.time()
        result = PDFExtractor().extract_sections_and_fields(self.pdf_path)
        print(f"✅ Form elements extracted in {time.time() - start:.2f}s")
        return result

    def generate_questions(
        self, form_elements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        print("✏️ Step 2: Generating questions from digital PDF fields...")
        start = time.time()
        result = QuestionGenerator().process_pdf(self.pdf_path)
        print(f"✅ Questions generated in {time.time() - start:.2f}s")
        return result

    def match_questions_to_blocks(self, form_elements, questions):  # not used
        return questions

    def summarize_documents(self) -> str:
        print("📄 Step 3: Summarizing EMR documents...")
        start = time.time()
        result = DocumentSummarizer().process_documents(
            [Path(f) for f in self.emr_files]
        )
        print(f"✅ Summary generated in {time.time() - start:.2f}s")
        return result

    def generate_answers(
        self, questions: List[Dict[str, Any]], summary: str
    ) -> List[Dict[str, Any]]:
        print("🤖 Step 4: Generating answers from EMR summary...")
        start = time.time()
        result = QuestionAnswerGenerator().process_questions(
            summary, questions
        )
        print(f"✅ Answers generated in {time.time() - start:.2f}s")
        return result

    def estimate_answer_boxes(
        self, matched_blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        print("ℹ️ Digital form detected — skipping answer box estimation.")
        return matched_blocks

    def fill_form(self, answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        print("📝 Step 5: Filling digital PDF form with answers...")
        output_pdf = self.output_dir / "filled_form.pdf"
        filler = DigitalPDFFiller()
        success = filler.fill_digital_form(
            answers_data=answers,
            pdf_path=self.pdf_path,
            output_pdf_path=output_pdf,
            save_debug_info=True,
            debug_dir=self.output_dir / "debug",
        )
        print("✅ Digital PDF filled")
        return {
            "success": success,
            "output_path": output_pdf,
            "fill_stats": filler.get_results(),
        }

    def save_outputs(self, questions, summary, answers, extras=None):
        print("💾 Saving output files:")
        self.output_dir.joinpath("questions.json").write_text(
            json.dumps(questions, indent=2)
        )
        print(
            "📁 Saved `questions.json` — all extracted questions from the form"
        )
        self.output_dir.joinpath("summary.txt").write_text(summary)
        print("📁 Saved `summary.txt` — summary of EMR content")
        self.output_dir.joinpath("answers.json").write_text(
            json.dumps(answers, indent=2)
        )
        print("📁 Saved `answers.json` — answers generated from summary")
        if extras:
            self.output_dir.joinpath("fill_stats.json").write_text(
                json.dumps(extras.get("fill_stats", {}), indent=2)
            )
            print("📁 Saved `fill_stats.json` — filling statistics")

    def run_pipeline(
        self, visualize_output: bool = False, save_files: bool = True
    ) -> Dict[str, Any]:
        print("📄 Running digital form processor pipeline...")
        start_all = time.time()

        form_elements = self.extract_form_elements()
        questions = self.generate_questions(form_elements)
        summary = self.summarize_documents()
        answers = self.generate_answers(questions, summary)
        fill_result = self.fill_form(answers)
        if visualize_output:
            print("Digital form don't support visualization.")
        if save_files:
            print("💾 Saving output files...")
            self.save_outputs(questions, summary, answers, extras=fill_result)

        if fill_result.get("output_path"):
            print(f"📄 ✅ Filled PDF saved to: {fill_result['output_path']}")

        print(
            f"✅ Digital pipeline complete in {time.time() - start_all:.2f}s"
        )
        return package_pipeline_output(
            questions, summary, answers, fill_result
        )
