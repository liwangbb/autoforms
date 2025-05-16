"""
Module: question_extractor.py
Extracts structured questions from form block text using Azure OpenAI.
"""

import re
from typing import Dict, List

from utils.azure_openai_helper import (
    chat_with_azure_openai,
    get_azure_openai_client_and_deployment,
    handle_openai_exceptions,
)


class QuestionExtractor:
    def __init__(self):
        self.client, self.deployment = get_azure_openai_client_and_deployment()

    def extract_questions(self, blocks: List[Dict]) -> str:
        """
        Combines block text and uses OpenAI to extract fillable questions.
        """
        combined_text = "\n\n".join([block["text"] for block in blocks])
        prompt = f"""
        Below is a medical form text. Extract all user-fillable questions.

        For each question, return:
        - Question (rephrased if needed)
        - Type: one of [text, yes_no, multiple_choice, checkbox, number, date]
        - Options (if applicable)

        Format:
        Q1. [question]
        Type: [type]
        Options: [comma-separated options]

        Only list the questions. No explanation.

        Text:
        \"\"\"
        {combined_text}
        \"\"\"
        """

        messages = [
            {
                "role": "system",
                "content": "You extract structured questions from text.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]
        try:
            response = chat_with_azure_openai(
                self.client,
                self.deployment,
                messages=messages,
                temperature=0.2,
                max_tokens=2000,
            )
            raw_output = response.choices[0].message.content.strip()

            return raw_output

        except Exception as e:
            handle_openai_exceptions(e)
            raise

    def parse_raw_questions(self, raw_text: str) -> List[Dict]:
        """
        Parses raw OpenAI output into a structured list of questions.
        """
        question_blocks = re.split(r"\nQ\d+\.\s*", raw_text)
        question_blocks = [qb.strip() for qb in question_blocks if qb.strip()]

        parsed_questions = []
        for block in question_blocks:
            question_match = re.match(r"(.*?)(\n|$)", block)
            type_match = re.search(r"Type:\s*(\w+)", block)
            options_match = re.search(r"Options:\s*(.*)", block)

            question_text = (
                question_match.group(1).strip() if question_match else ""
            )
            question_type = (
                type_match.group(1).strip().lower() if type_match else "text"
            )
            options = (
                [opt.strip() for opt in options_match.group(1).split(",")]
                if options_match
                else []
            )

            parsed_questions.append(
                {
                    "key": f"Q{len(parsed_questions) + 1}",
                    "generated_question": question_text,
                    "type": question_type,
                    "options": options if options != [""] else [],
                }
            )

        return parsed_questions
