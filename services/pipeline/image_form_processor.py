import json
import time
from pathlib import Path
from typing import Any, Dict, List

from services.answer_generator import QuestionAnswerGenerator
from services.image_pdf.adaptive_analyzer import AdaptiveFormAnalyzer
from services.image_pdf.image_pdf_filler import ImagePDFfiller
from services.image_pdf.pdf_block_combiner import FormBlockCombiner
from services.image_pdf.pdf_parser import DocAIParser
from services.image_pdf.question_extractor import QuestionExtractor
from services.image_pdf.question_matcher import QuestionBlockMatcher
from services.pipeline.form_processor_base import BaseFormProcessor
from services.summarize_data import DocumentSummarizer
from utils.pdf_helper import package_pipeline_output, visualize


class ImageFormProcessor(BaseFormProcessor):
    def extract_form_elements(self) -> List[Dict[str, Any]]:
        print("📄 Step 1: Extracting form elements from image-based PDF...")
        start = time.time()
        parser = DocAIParser(self.pdf_path)
        segments = parser.extract_segments()
        combiner = FormBlockCombiner()
        grouped_uids = combiner.combine_with_openai(segments)
        blocks = combiner.merge_segments_by_uids(segments, grouped_uids)
        print(
            f"✅ Form elements extracted in {time.time() - start:.2f} seconds."
        )
        return blocks

    def generate_questions(
        self, form_elements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        print("🧠 Step 2: Generating questions using OpenAI...")
        start = time.time()
        extractor = QuestionExtractor()
        raw_text = extractor.extract_questions(form_elements)
        questions = extractor.parse_raw_questions(raw_text)
        print(f"✅ Questions generated in {time.time() - start:.2f} seconds.")
        return questions

    def match_questions_to_blocks(
        self,
        form_elements: List[Dict[str, Any]],
        questions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        print("🔗 Step 3: Matching questions to form blocks...")
        start = time.time()
        matcher = QuestionBlockMatcher()
        matched = matcher.insert_questions_into_blocks(
            questions, form_elements
        )
        print(f"✅ Questions matched in {time.time() - start:.2f} seconds.")
        return matched

    def estimate_answer_boxes(
        self, matched_blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        print("📐 Step 4: Estimating answer box locations...")
        start = time.time()
        analyzer = AdaptiveFormAnalyzer(matched_blocks)
        estimated = analyzer.estimate_answer_boxes()
        print(
            f"✅ Answer boxes estimated in {time.time() - start:.2f} seconds."
        )
        return estimated

    def summarize_documents(self) -> str:
        print("📑 Step 5: Summarizing EMR documents...")
        start = time.time()
        summarizer = DocumentSummarizer()
        summary = summarizer.process_documents(
            [Path(f) for f in self.emr_files]
        )
        print(f"✅ Summary generated in {time.time() - start:.2f} seconds.")
        return summary

    def generate_answers(
        self, questions: List[Dict[str, Any]], summary: str
    ) -> List[Dict[str, Any]]:
        print("💬 Step 6: Generating answers from summary...")
        start = time.time()
        generator = QuestionAnswerGenerator()
        answers = generator.process_questions(
            summary_text=summary, questions=questions
        )
        print(f"✅ Answers generated in {time.time() - start:.2f} seconds.")
        return answers

    def fill_form(
        self, matched_blocks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        print("✍️ Step 7: Filling image-based form with answers...")
        try:
            filler = ImagePDFfiller(log_level=100)  # Disable logging
            filled_pdf_path = self.output_dir / "filled_form.pdf"
            filler.fill_pdf_with_answers(
                str(self.pdf_path), matched_blocks, str(filled_pdf_path)
            )
            return {
                "success": True,
                "output_path": str(filled_pdf_path),
                "fill_stats": {"message": "Form filled successfully."},
            }
        # pylint: disable=broad-exception-caught
        except Exception as e:
            return {
                "success": False,
                "output_path": None,
                "fill_stats": {"message": f"Filling failed: {e}"},
            }

    def save_outputs(
        self,
        questions: List[Dict],
        summary: str,
        answers: List[Dict],
        extras: Dict = None,
    ):
        print("💾 Saving output files...")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        summary_path = self.output_dir / "summary.txt"
        summary_path.write_text(summary)
        print(f"📄 Saved: {summary_path.name} — Summary of EMR documents.")

        answers_path = self.output_dir / "answers.json"
        answers_path.write_text(json.dumps(answers, indent=2))
        print(f"📄 Saved: {answers_path.name} — List of answers.")

        blocks_path = self.output_dir / "final_blocks.json"
        blocks_path.write_text(json.dumps(questions, indent=2))
        print(
            f"📄 Saved: {blocks_path.name} — "
            "Full structure of grouped form blocks with inserted questions, "
            "answer boxes, and answers."
        )

        if extras:
            stats_path = self.output_dir / "fill_stats.json"
            stats_path.write_text(
                json.dumps(extras.get("fill_stats", {}), indent=2)
            )
        print(
            f"📄 Saved: {stats_path.name} — "
            "Metadata about form filling process (placeholder for image PDF)."
        )

    def _map_estimated_boxes(self, matched_blocks, estimated_blocks):
        uid_to_estimated = {e["uid"]: e for e in estimated_blocks}
        for block in matched_blocks:
            est = uid_to_estimated.get(block["uid"])
            if est and est.get("answer_box_norm"):
                block["answer_box_norm"] = est["answer_box_norm"]

    def _attach_answers(self, matched_blocks, answers):
        key_to_answer = {
            a["key"]: a["answers"] for a in answers if a.get("key")
        }
        for block in matched_blocks:
            for q in block.get("questions", []):
                q["answers"] = key_to_answer.get(q["key"])

    def run_pipeline(
        self, visualize_output: bool = False, save_files: bool = True
    ) -> Dict[str, Any]:
        print("🖼️ Running image form processor pipeline...")
        start_all = time.time()
        form_elements = self.extract_form_elements()
        questions = self.generate_questions(form_elements)
        matched_blocks = self.match_questions_to_blocks(
            form_elements, questions
        )

        estimated_blocks = self.estimate_answer_boxes(matched_blocks)

        self._map_estimated_boxes(matched_blocks, estimated_blocks)

        summary = self.summarize_documents()
        answers = self.generate_answers(questions, summary)

        self._attach_answers(matched_blocks, answers)

        for block in form_elements:
            block.pop("box", None)
            block.pop("label", None)

        fill_result = self.fill_form(matched_blocks)

        if visualize_output:
            visualize(estimated_blocks, output_dir=str(self.output_dir))

        if save_files:
            self.save_outputs(
                matched_blocks, summary, answers, extras=fill_result
            )

        if fill_result.get("output_path"):
            print(f"📄 ✅ Filled PDF saved to: {fill_result['output_path']}")
        else:
            print("⚠️ Form filling failed or no output was generated.")

        print(f"✅ Image pipeline complete in {time.time() - start_all:.2f}s")
        return package_pipeline_output(
            questions, summary, answers, fill_result
        )
