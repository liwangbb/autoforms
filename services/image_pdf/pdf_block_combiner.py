"""
Module: form_block_combiner.py
Combines PDF form segments into blocks using Azure OpenAI.
"""

from typing import Dict, List

from utils.azure_openai_helper import (
    chat_with_azure_openai,
    get_azure_openai_client_and_deployment,
    handle_openai_exceptions,
)


class FormBlockCombiner:
    def __init__(self):
        try:
            self.client, self.deployment = (
                get_azure_openai_client_and_deployment()
            )
        except Exception as e:
            handle_openai_exceptions(e)
            raise

    def combine_with_openai(self, segments: List[Dict]) -> List[List[str]]:
        numbered_text = "\n".join(
            [f"{seg['text']} (uid: {seg['uid']})" for seg in segments]
        )

        user_prompt = {
            "role": "user",
            "content": (
                "Here is the raw content I extracted from "
                "an image-based PDF, which is a form, "
                "and includes some questions that need to be "
                "filled in by users.\n\n"
                f"Content of the pdf:\n{numbered_text}\n\n"
                "Please group the data into question blocks. "
                "Since it's a form, you should combine "
                "the question and the options "
                "(e.g., checkboxes) into a single group. "
                "Treat each label field "
                "(like name, date, policy number) "
                "as a separate block "
                "unless it's clearly part of a question + options structure. "
                "Just output the uid groups as raw text, "
                "one group per line like this:\n"
                "seg1, seg2\nseg3\nseg4, seg5, seg6"
            ),
        }

        messages = [
            {
                "role": "system",
                "content": (
                    "You group form segments into logical blocks "
                    "using their uids."
                ),
            },
            user_prompt,
        ]

        try:
            response = chat_with_azure_openai(
                self.client,
                self.deployment,
                messages,
                temperature=0.5,
                max_tokens=1000,
            )
            reply = response.choices[0].message.content
            return self._parse_uid_groups(reply)

        except Exception as e:
            handle_openai_exceptions(e)
            raise

    def _parse_uid_groups(self, text_response: str) -> List[List[str]]:
        groups = []
        for line in text_response.strip().splitlines():
            uids = [uid.strip() for uid in line.split(",") if uid.strip()]
            if uids:
                groups.append(uids)
        return groups

    def merge_segments_by_uids(
        self, segments: List[Dict], grouped_uids: List[List[str]]
    ) -> List[Dict]:
        segment_map = {s["uid"]: s for s in segments}
        combined = []

        for i, uid_group in enumerate(grouped_uids):
            texts, segs, all_uids, max_page = self._collect_segment_data(
                uid_group, segment_map
            )
            boxes_on_max_page = [
                seg["box"]
                for seg in segs
                if seg.get("pageNumber", 1) == max_page
                and all(
                    k in seg.get("box", {}) for k in ["x1", "y1", "x2", "y2"]
                )
            ]

            if not boxes_on_max_page:
                continue

            merged_box = self._merge_boxes(boxes_on_max_page)

            combined.append(
                {
                    "uid": f"group{i+1}",
                    "segments": all_uids,
                    "pageNumber": max_page,
                    "text": " ".join(texts),
                    "question_box_norm": merged_box,
                }
            )

        return combined

    def _collect_segment_data(
        self, uid_group: List[str], segment_map: Dict[str, Dict]
    ) -> tuple:
        texts = []
        segs = []
        all_uids = []
        max_page = 1

        for uid in uid_group:
            seg = segment_map.get(uid)
            if seg:
                segs.append(seg)
                texts.append(seg["text"])
                all_uids.append(seg["uid"])
                max_page = max(max_page, seg.get("pageNumber", 1))

        return texts, segs, all_uids, max_page

    def _merge_boxes(self, boxes: List[Dict]) -> Dict:
        x1 = min(b["x1"] for b in boxes)
        y1 = min(b["y1"] for b in boxes)
        x2 = max(b["x2"] for b in boxes)
        y2 = max(b["y2"] for b in boxes)
        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
