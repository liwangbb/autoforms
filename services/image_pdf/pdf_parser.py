"""
Module: pdf_parser.py
This module defines a class to extract text segments and bounding box vertices
from image-based PDFs using Google Document AI.
"""

from typing import Any, Dict, List

from utils.docai_client import send_docai_request


class DocAIParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.response = send_docai_request(pdf_path)
        self.doc = {}
        self.full_text = ""
        self.pages = []
        self.segments = []

        if self.response:
            self.doc = self.response.get("document", {})
            self.full_text = self.doc.get("text", "")
            self.pages = self.doc.get("pages", [])
            print(
                f"✅ Response received. Doc contains {len(self.pages)} page(s)."
            )
        else:
            print("❌ Failed to get a valid response from Document AI.")

    def extract_segments(self) -> List[Dict[str, Any]]:
        if not self.full_text:
            print("⚠️ No full text found in OCR result.")
            return []

        self.segments = []
        segment_counter = 1

        for page in self.pages:
            page_number = page.get("pageNumber", 0)
            page_width = page.get("dimension", {}).get("width", 1)
            page_height = page.get("dimension", {}).get("height", 1)

            for paragraph in page.get("paragraphs", []):
                layout = paragraph.get("layout", {})
                anchor = layout.get("textAnchor", {})
                segments = anchor.get("textSegments", [])
                bounding_poly = layout.get("boundingPoly", {})

                for segment in segments:
                    page_meta = {
                        "page_number": page_number,
                        "page_width": page_width,
                        "page_height": page_height,
                    }
                    seg = self.create_segment(
                        segment_counter, segment, bounding_poly, page_meta
                    )

                    if seg:
                        self.segments.append(seg)
                        segment_counter += 1

        if not self.segments:
            print("⚠️ No segments found.")
        else:
            print(f"✅ Extracted {len(self.segments)} segments.")
        return self.segments

    def create_segment(
        self,
        uid_index: int,
        segment: Dict,
        bounding_poly: Dict,
        page_meta: Dict,
    ) -> Dict[str, Any] | None:
        start = int(segment.get("startIndex", 0))
        end = int(segment.get("endIndex", 0))
        text = self.full_text[start:end].strip()

        if not text:
            return None

        box = self._parse_bounding_box(bounding_poly, page_meta)
        if not box:
            return None

        return {
            "uid": f"seg{uid_index}",
            "text": text,
            "pageNumber": page_meta["page_number"],
            "box": box,
        }

    def _parse_bounding_box(
        self, bounding_poly: Dict, page_meta: Dict
    ) -> Dict[str, float] | None:
        normalized_vertices = bounding_poly.get("normalizedVertices", [])
        vertices = bounding_poly.get("vertices", [])

        if len(normalized_vertices) == 4:
            x_vals = [v.get("x", 0.0) for v in normalized_vertices]
            y_vals = [v.get("y", 0.0) for v in normalized_vertices]
        elif len(vertices) == 4:
            w, h = page_meta["page_width"], page_meta["page_height"]
            x_vals = [v.get("x", 0) / w for v in vertices]
            y_vals = [v.get("y", 0) / h for v in vertices]
        else:
            return None

        return {
            "x1": round(min(x_vals), 6),
            "y1": round(min(y_vals), 6),
            "x2": round(max(x_vals), 6),
            "y2": round(max(y_vals), 6),
        }
