"""
Module: question_generator.py
This module generate structured questions from digital forms
using AI services.
"""

import json
import logging

from services.digital_pdf.extractor import PDFExtractor
from utils.azure_openai_helper import (
    SUPPORTED_OPENAI_EXCEPTIONS,
    chat_with_azure_openai,
    get_azure_openai_client_and_deployment,
    handle_openai_exceptions,
)


class QuestionGenerator:
    def __init__(self):
        self.client, self.deployment = get_azure_openai_client_and_deployment()
        self.extractor = PDFExtractor()
        self.next_key_index = 1
        logging.info("✅ OpenAI client initialized successfully.")

    def generate_questions(self, section_data, batch_size=10):
        fields = section_data["fields"]
        self._add_keys_to_fields(fields)

        all_responses = self._process_field_batches(
            section_data["section_text"], fields, batch_size
        )

        processed_questions = self._convert_responses_to_json(all_responses)
        self._merge_questions_with_original_data(
            section_data, processed_questions
        )

        return section_data

    def _add_keys_to_fields(self, fields):
        """Add unique keys to fields that don't have them."""
        for field in fields:
            if "key" not in field:
                field["key"] = f"Q{self.next_key_index}"
                self.next_key_index += 1

    def _process_field_batches(self, section_text, fields, batch_size):
        all_responses = []

        for i in range(0, len(fields), batch_size):
            batch_fields = fields[i : i + batch_size]
            batch_fields_with_keys = self._prepare_batch_fields(batch_fields)
            fields_text = json.dumps(batch_fields_with_keys, indent=2)

            messages = self._create_prompt_messages(section_text, fields_text)

            try:
                response = chat_with_azure_openai(
                    self.client, self.deployment, messages
                )
                raw_content = response.choices[0].message.content.strip()
                all_responses.append(raw_content)
            except SUPPORTED_OPENAI_EXCEPTIONS as e:
                handle_openai_exceptions(e)
                all_responses.append([])

        return all_responses

    def _prepare_batch_fields(self, batch_fields):
        batch_fields_with_keys = []
        for field in batch_fields:
            batch_fields_with_keys.append(
                {
                    "key": field["key"],
                    "field_name": (
                        field["field_name"]
                        if "field_name" in field
                        else field["name"]
                    ),
                    "type": field["type"] if "type" in field else "",
                    "options": (
                        field["options"] if "options" in field else None
                    ),
                }
            )
        return batch_fields_with_keys

    def _create_prompt_messages(self, section_text, fields_text):
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that"
                    "generates questions for medical form fields. "
                    "You must ALWAYS return the unique key for"
                    "each field exactly as provided."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Here is a section content of a medical form:"
                    f"\n\n{section_text}\n\n"
                    "Below are the fields with their unique keys, "
                    "names, types, and options of the section:\n"
                    f"{fields_text}\n\n"
                    "Generate relevant questions for EVERY field "
                    "listed above based on their context.\n"
                    "Return ONLY the following structured "
                    "text format (not JSON):\n\n"
                    "Key: <unique_key>\n"
                    "Generated Question: <generated_question>\n"
                    "---\n"
                    "IMPORTANT: "
                    "You MUST include the unique key"
                    "for each field exactly as provided.\n"
                    "**DO NOT** return any other information"
                    "Like field names, types, or options.\n"
                    "**DO NOT** return in JSON format.\n"
                    "**DO NOT** generate new fields.\n"
                    "Use ONLY the structured text format above."
                ),
            },
        ]

    def _convert_responses_to_json(self, raw_responses):
        all_parsed_data = []

        is_list = isinstance(raw_responses, list)
        converted_responses = (
            list(raw_responses) if is_list else [raw_responses]
        )
        responses_to_process = converted_responses

        for raw_text in responses_to_process:
            if not isinstance(raw_text, str):
                continue

            fields = self._parse_fields_from_text(raw_text)
            all_parsed_data.extend(fields)

        return all_parsed_data

    def _parse_fields_from_text(self, raw_text):
        fields = []
        current_field = {}

        for line in raw_text.split("\n"):
            line = line.strip()

            if line == "---":
                self._append_and_reset_field(fields, current_field)
                current_field = {}
                continue

            if line.startswith("Key:"):
                self._append_and_reset_field(fields, current_field)
                current_field = {
                    "key": line.removeprefix("Key:").strip(),
                }
                continue

            if line.startswith("Generated Question:"):
                question_text = line.removeprefix(
                    "Generated Question:"
                ).strip()
                current_field["generated_question"] = question_text
                continue

        self._append_and_reset_field(fields, current_field)

        return fields

    def _append_and_reset_field(self, fields, current_field):
        if (
            current_field
            and "key" in current_field
            and "generated_question" in current_field
        ):
            fields.append(current_field)

    def _parse_options(self, options_text):
        if options_text.lower() == "none":
            return None

        cleaned_options = self._clean_options(options_text)
        return cleaned_options if cleaned_options else None

    def _clean_options(self, options_text):
        if isinstance(options_text, list):
            options_text = str(options_text)
        if options_text.startswith("[") and options_text.endswith("]"):
            options_text = options_text[1:-1]

        options = []
        current = ""
        in_quotes = False

        for char in options_text:
            if char == '"' and (not current or current[-1] != "\\"):
                in_quotes = not in_quotes
                current += char
            elif char == "," and not in_quotes:
                options.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            options.append(current.strip())

        cleaned_options = []
        for opt in options:
            opt = opt.strip()
            if (opt.startswith('"') and opt.endswith('"')) or (
                opt.startswith("'") and opt.endswith("'")
            ):
                opt = opt[1:-1]

            opt = opt.replace('\\"', '"').replace("\\'", "'")

            if opt.startswith('"') and opt.endswith('"'):
                opt = opt[1:-1]

            if opt:
                cleaned_options.append(opt)

        return cleaned_options

    def _merge_questions_with_original_data(
        self, section_data, processed_questions
    ):
        # Create a dictionary of questions indexed by key
        questions_by_key = {
            q["key"]: q["generated_question"]
            for q in processed_questions
            if "key" in q and "generated_question" in q
        }

        # Update original fields with generated questions
        for field in section_data["fields"]:
            if field["key"] in questions_by_key:
                field["generated_question"] = questions_by_key[field["key"]]
                # Make sure field has field_name instead of just name
                if "name" in field and "field_name" not in field:
                    field["field_name"] = field["name"]

    def process_pdf(self, file_path, batch_size=10):
        extracted_data = self.extractor.extract_sections_and_fields(file_path)
        all_processed_fields = []

        for section_data in extracted_data:
            processed_section = self.generate_questions(
                section_data, batch_size=batch_size
            )

            if "fields" in processed_section:
                for field in processed_section["fields"]:
                    simplified_field = {
                        "field_name": field.get("field_name", ""),
                        "type": field.get("type", ""),
                        "options": field.get("options", None),
                        "key": field.get("key", ""),
                        "generated_question": field.get(
                            "generated_question", ""
                        ),
                    }
                    all_processed_fields.append(simplified_field)

        return all_processed_fields
