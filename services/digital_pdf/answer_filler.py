import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class DigitalPDFFiller:
    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        if logger is None:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(levelname)s - %(message)s",
            )
            self.logger = logging.getLogger("digital_pdf_filler")
        else:
            self.logger = logger

        self.successfully_filled = 0
        self.skipped_fields = []
        self.fill_errors = []
        self.fill_data = {}
        self.total_fields_in_answers = 0
        self.fields_filled_back = 0

    def process_answers(
        self,
        answers_data: Union[str, Path, List[Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        if isinstance(answers_data, (str, Path)):
            return self._load_answers_from_json(answers_data)

        fill_data = {}

        if isinstance(answers_data, list):
            for item in answers_data:
                field_name = item.get("field_name")
                answer = item.get("answers")
                if answer is None or answer == "":
                    continue
                if isinstance(answer, list):
                    answer = ", ".join(str(a) for a in answer if a)
                fill_data[field_name] = {
                    "value": answer,
                    "type": item.get("type", "text"),
                    "options": item.get("options"),
                }
        elif isinstance(answers_data, dict):
            for field_name, answer in answers_data.items():
                fill_data[field_name] = {
                    "value": answer,
                    "type": "text",
                    "options": None,
                }
        else:
            raise TypeError(
                f"Expected str, Path, list or dict, got {type(answers_data)}"
            )

        self.fill_data = fill_data
        self.total_fields_in_answers = len(fill_data)
        return fill_data

    def _load_answers_from_json(
        self, answers_json_path: Union[str, Path]
    ) -> Dict[str, Any]:
        self.logger.info("Loading answers from %s", answers_json_path)
        with open(answers_json_path, "r", encoding="utf-8") as f:
            answers_data = json.load(f)
        return self.process_answers(answers_data)

    def normalize_checkbox_value(
        self, value: str, options: Optional[List[str]]
    ) -> str:
        if not options:
            return (
                "Yes"
                if str(value).lower() in ["true", "yes", "on", "1"]
                else "Off"
            )
        for option in options:
            if str(value).lower() == option.lower():
                return option
        return "Off"

    def prepare_fields(self):
        for field_name, meta in self.fill_data.items():
            if meta.get("type", "text").lower() == "checkbox":
                meta["value"] = self.normalize_checkbox_value(
                    meta["value"], meta.get("options")
                )

    def create_fdf(self, fields: Dict[str, Dict[str, Any]]) -> str:
        fdf = [
            "%FDF-1.2\n",
            "1 0 obj\n",
            "<<\n",
            "/FDF\n",
            "<<\n",
            "/Fields [\n",
        ]

        filled_count = 0
        for key, meta in fields.items():
            value = str(meta["value"])
            if value.strip() == "":
                continue  # Skip empty values
            key = key.replace("(", "\\(").replace(")", "\\)")
            value = value.replace("(", "\\(").replace(")", "\\)")
            fdf.append(f"<< /T ({key}) /V ({value}) >>\n")
            filled_count += 1

        self.fields_filled_back = filled_count

        fdf.extend(
            [
                "]\n",
                ">>\n",
                ">>\n",
                "endobj\n",
                "trailer\n",
                "<</Root 1 0 R>>\n",
                "%%EOF\n",
            ]
        )
        return "".join(fdf)

    def fill_with_pdftk(self, pdf_path: str, output_path: str) -> bool:
        try:
            fdf_str = self.create_fdf(self.fill_data)
            fdf_path = "temp_data.fdf"
            with open(fdf_path, "w", encoding="utf-8") as f:
                f.write(fdf_str)

            # Fill PDF form WITHOUT flattening — keeps fields editable
            subprocess.run(
                [
                    "pdftk",
                    pdf_path,
                    "fill_form",
                    fdf_path,
                    "output",
                    output_path,
                ],
                check=True,
            )

            os.remove(fdf_path)
            self.logger.info(
                "Successfully saved modifiable filled PDF to: %s", output_path
            )
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"pdftk failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return False

    def fill_digital_form(
        self,
        answers_data: Union[str, Path, List[Dict[str, Any]], Dict[str, Any]],
        pdf_path: Union[str, Path],
        output_pdf_path: Union[str, Path],
        save_debug_info: bool = False,
        debug_dir: Optional[Union[str, Path]] = None,
        save_answers_json: bool = False,
        field_type_handling: bool = True,
    ) -> bool:
        self.successfully_filled = 0
        self.skipped_fields = []
        self.fill_errors = []
        self.total_fields_in_answers = 0
        self.fields_filled_back = 0

        if (save_debug_info or save_answers_json) and debug_dir:
            os.makedirs(debug_dir, exist_ok=True)

        self.process_answers(answers_data)

        if field_type_handling:
            self.prepare_fields()

        return self.fill_with_pdftk(str(pdf_path), str(output_pdf_path))

    def get_results(self) -> Dict[str, Any]:
        return {
            "successfully_filled": self.successfully_filled,
            "skipped_fields": self.skipped_fields,
            "fill_errors": self.fill_errors,
            "total_fields_in_answers": self.total_fields_in_answers,
            "fields_filled_back": self.fields_filled_back,
            "fill_percentage": (
                round(
                    100
                    * self.fields_filled_back
                    / self.total_fields_in_answers,
                    2,
                )
                if self.total_fields_in_answers
                else 0.0
            ),
        }
