"""
Module: summarize_data.py
This module summarize documents from emr to answer questions
using AI services.
"""

import logging

from utils.azure_openai_helper import (
    SUPPORTED_OPENAI_EXCEPTIONS,
    chat_with_azure_openai,
    get_azure_openai_client_and_deployment,
    handle_openai_exceptions,
)

logger = logging.getLogger(__name__)


class DocumentSummarizer:
    def __init__(self):
        self.client, self.deployment = get_azure_openai_client_and_deployment()

    def read_text_file(self, file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
        return content

    def summarize_text_with_openai(self, text):
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant summarizing medical documents."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Summarize the key details of this medical document:\n\n"
                    f"{text}"
                ),
            },
        ]
        try:
            response = chat_with_azure_openai(
                self.client, self.deployment, messages, temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except SUPPORTED_OPENAI_EXCEPTIONS as e:
            handle_openai_exceptions(e)
            return ""

    def process_documents(self, input_files):
        all_summaries = []
        if isinstance(input_files, str):
            summary = self.summarize_text_with_openai(input_files)
            all_summaries.append(f"===== Text Input =====\n{summary}\n\n")
        else:
            for file_path in input_files:
                text = self.read_text_file(file_path)
                summarized_text = self.summarize_text_with_openai(text)
                all_summaries.append(
                    f"===== {file_path} =====\n{summarized_text}\n\n"
                )
        combined_summary = "\n\n".join(all_summaries)
        return combined_summary
