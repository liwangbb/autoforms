"""
Module: question_matcher.py
Matches extracted questions to their corresponding
form blocks using Azure OpenAI.
"""

import re
from typing import Dict, List

from utils.azure_openai_helper import (
    chat_with_azure_openai,
    get_azure_openai_client_and_deployment,
    handle_openai_exceptions,
)


class QuestionBlockMatcher:
    def __init__(self):
        self.client, self.deployment = get_azure_openai_client_and_deployment()

    def match_question_to_block(
        self, question: str, blocks: List[Dict]
    ) -> Dict:
        """
        Matches a single question to the most relevant block.
        """
        choices = "\n".join(
            [f"{i+1}. {block['text']}" for i, block in enumerate(blocks)]
        )
        prompt = f"""
You're helping match a question to the most
relevant form block from a medical form.
Question: "{question}"
Ignore blocks that are just headers, footers, fax information,
or metadata. Only choose blocks that contain user-facing
content that could relate to this question.

Here are the blocks:

{choices}

Which block best matches the question? Respond with the block number only.
"""

        try:
            response = chat_with_azure_openai(
                self.client,
                self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "You're a form mapping assistant.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=200,
            )
            answer = response.choices[0].message.content.strip()
            index = int(re.findall(r"\d+", answer)[0]) - 1
            if 0 <= index < len(blocks):
                return blocks[index]

        except Exception as e:
            handle_openai_exceptions(e)
            raise
        return None

    def insert_questions_into_blocks(
        self, questions: List[Dict], blocks: List[Dict]
    ) -> List[Dict]:
        """
        Matches and inserts questions into corresponding blocks.
        """
        for q in questions:
            matched_block = self.match_question_to_block(
                q["generated_question"], blocks
            )
            if matched_block:
                matched_block.setdefault("questions", []).append(q)
        return blocks
