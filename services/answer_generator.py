"""
Module: answer_generator.py
This module uses summarized documents from EMR to answer questions
using AI services.
"""

import ast
import logging
from typing import Any, Dict, List, Optional, Union

from utils.azure_openai_helper import (
    SUPPORTED_OPENAI_EXCEPTIONS,
    chat_with_azure_openai,
    get_azure_openai_client_and_deployment,
    handle_openai_exceptions,
)

logger = logging.getLogger(__name__)


class QuestionAnswerGenerator:
    """Generates answers to questions using summarized EMR data and AI."""

    def __init__(self):
        self.client, self.deployment = get_azure_openai_client_and_deployment()

    def get_deployment_name(self) -> str:
        return self.deployment

    def process_questions(
        self, summary_text: str, questions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        # Extract questions with keys for processing
        questions_with_keys = [q for q in questions if "key" in q]
        original_questions = {q["key"]: q for q in questions_with_keys}
        processed_keys = set()
        all_answers = []
        batch_size = 10

        # Process questions in batches
        for i in range(0, len(questions_with_keys), batch_size):
            batch = questions_with_keys[i : i + batch_size]

            try:
                questions_text = self._construct_batch_prompt(batch)
                response_text = self._send_to_openai_and_parse(
                    questions_text, summary_text
                )
                parsed = self._parse_responses(response_text)

                # Process successful answers
                self._process_parsed_answers(
                    parsed, original_questions, all_answers, processed_keys
                )

            # pylint: disable=broad-exception-caught
            except Exception as e:
                logger.error("Failed to summarize: %s", e)
                return []

        # Handle any remaining unprocessed questions
        self._handle_missing_answers(
            original_questions.keys(),
            processed_keys,
            original_questions,
            all_answers,
        )

        return all_answers

    def _process_parsed_answers(
        self,
        parsed: List[Dict[str, Any]],
        original_questions: Dict[str, Dict[str, Any]],
        all_answers: List[Dict[str, Any]],
        processed_keys: set,
    ) -> None:
        for answer_item in parsed:
            key = answer_item["key"]
            if key in original_questions:
                complete_item = original_questions[key].copy()
                raw_answer = answer_item["answers"]
                sanitized_answer = self._sanitize_answer(
                    raw_answer, original_questions[key]
                )
                complete_item["answers"] = sanitized_answer
                all_answers.append(complete_item)
                processed_keys.add(key)

    def _handle_missing_answers(
        self,
        keys: List[str],
        processed_keys: set,
        original_questions: Dict[str, Dict[str, Any]],
        all_answers: List[Dict[str, Any]],
    ) -> None:
        for key in keys:
            if key not in processed_keys and key in original_questions:
                complete_item = original_questions[key].copy()
                complete_item["answers"] = None
                all_answers.append(complete_item)
                processed_keys.add(key)

    def _construct_batch_prompt(self, questions: List[Dict[str, Any]]) -> str:
        prompt_lines = []
        for q in questions:
            if "key" not in q:
                continue
            options = (
                ", ".join(q.get("options", [])) if q.get("options") else "N/A"
            )
            prompt_lines.append(
                f"Key: {q['key']}\n"
                f"Question: {q.get('generated_question', '')}\n"
                f"Type: {q.get('type', 'text')}\n"
                f"Options: {options}"
            )
        return "\n\n".join(prompt_lines)

    def _send_to_openai_and_parse(
        self, questions_text: str, summary_text: str
    ) -> Union[str, List]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant answering medical-related "
                    "questions based on the provided medical document."
                    "For checkbox questions, ensure "
                    "answers match the available options."
                    "Do not use external knowledge "
                    "beyond what's in the summary. "
                    "Your response format must be EXACTLY as specified."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Using the following medical document, "
                    f"answer these questions concisely:\n\n"
                    f"Medical Document:\n{summary_text}\n\n"
                    f"Questions:\n{questions_text}\n\n"
                    "Provide answers in this EXACT format for each question:\n"
                    "Key: <question_key>\n"
                    "Answer: <answer>\n"
                    "---\n"
                    "\nExample:\n"
                    "Key: Q1\n"
                    "Answer: 120/80\n"
                    "---\n"
                    "Key: Q2\n"
                    "Answer: Yes\n"
                    "---\n"
                    "\nIf a question cannot be answered, use:\n"
                    "Key: <question_key>\n"
                    "Answer: null\n"
                    "---\n"
                ),
            },
        ]

        # Default return value for error cases
        result = []

        try:
            response = chat_with_azure_openai(
                self.client, self.deployment, messages
            )
            result = response.choices[0].message.content.strip()

        except SUPPORTED_OPENAI_EXCEPTIONS as e:
            handle_openai_exceptions(e)

        return result

    def _sanitize_answer(
        self, answer: Optional[str], field_data: Dict[str, Any]
    ) -> Optional[str]:
        if not answer:
            return None

        try:
            parsed = ast.literal_eval(answer)
            if isinstance(parsed, list) and parsed:
                answer = parsed[0]
        except (SyntaxError, ValueError):
            # Ignore parsing errors, use answer as is
            pass

        answer = str(answer).strip().strip("\"'")

        if field_data.get("type", "").lower() in (
            "checkbox",
            "radio",
            "select",
        ) and field_data.get("options"):
            options_raw = field_data.get("options")
            try:
                options = (
                    options_raw
                    if isinstance(options_raw, list)
                    else ast.literal_eval(options_raw)
                )
                if isinstance(options, list):
                    # Try exact match first
                    for option in options:
                        if answer.lower() == option.lower():
                            return option
                    # Try partial match as fallback
                    for option in options:
                        if (
                            answer.lower() in option.lower()
                            or option.lower() in answer.lower()
                        ):
                            return option
            except (SyntaxError, ValueError) as e:
                logger.warning("Error parsing options: %s", str(e))

        return answer

    def _parse_responses(self, response_text: str) -> List[Dict[str, Any]]:
        structured_data = []

        response_blocks = response_text.strip().split("---")

        for block in response_blocks:
            block = block.strip()
            if not block:
                continue

            key_value = None
            answer_value = None

            lines = block.split("\n")
            for line in lines:
                line = line.strip()
                if line.lower().startswith("key:"):
                    key_value = line[4:].strip()
                elif line.lower().startswith("answer:"):
                    answer_value = line[7:].strip()

            if key_value:
                if answer_value and answer_value.lower() == "null":
                    answer = None
                else:
                    answer = answer_value

                structured_data.append({"key": key_value, "answers": answer})

        return structured_data
