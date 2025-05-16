from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class BaseFormProcessor(ABC):
    def __init__(self, pdf_path: str, emr_files: List[str], output_dir: Path):
        self.pdf_path = pdf_path
        self.emr_files = emr_files
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def extract_form_elements(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def generate_questions(
        self, form_elements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def match_questions_to_blocks(
        self,
        form_elements: List[Dict[str, Any]],
        questions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def summarize_documents(self) -> str:
        pass

    @abstractmethod
    def generate_answers(
        self, questions: List[Dict[str, Any]], summary: str
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def fill_form(self, answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def save_outputs(
        self,
        questions: List[Dict],
        summary: str,
        answers: List[Dict],
        extras: Dict = None,
    ):
        pass

    @abstractmethod
    def run_pipeline(self):
        pass

    @abstractmethod
    def estimate_answer_boxes(
        self, matched_blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        pass
