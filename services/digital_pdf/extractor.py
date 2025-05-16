"""
Module: extractor.py
This module extract text and form fields from digital PDFs.
"""

import logging

import pdfplumber
import PyPDF2

from services.digital_pdf.scorer import FieldScorer


class PDFExtractor:
    def __init__(self):
        logging.info("Initializing PDF Extractor")

    def extract_sections_and_fields(self, file_path):
        with open(file_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            pdf = pdfplumber.open(file)

            field_groups = self.initialize_field_groups(reader, pdf)
            fields = reader.get_fields()
            self._assign_fields_to_pages(fields, reader, field_groups)

            return self._format_extracted_data(field_groups)

    def initialize_field_groups(self, reader, pdf):
        field_groups = {}
        for i, (page, pdf_page) in enumerate(zip(reader.pages, pdf.pages)):
            text = page.extract_text()
            visible_text = self._extract_visible_text(pdf_page)
            page_num = i + 1

            field_groups[page_num] = {
                "section_text": text.strip() if text else "",
                "visible_text": visible_text,
                "fields": [],
            }
        return field_groups

    def _extract_visible_text(self, pdf_page):
        words = pdf_page.extract_words()
        visible_text = [word["text"] for word in words]
        return visible_text

    def _assign_fields_to_pages(self, fields, reader, field_groups):
        for field_name, field_info in fields.items():
            field_type = self._determine_field_type(field_info)
            options = self._extract_field_options(field_info, reader)
            scorer = FieldScorer()
            field_page_index = scorer.field_page_detection(
                field_name, field_groups, options=options
            )

            if field_page_index is None:
                field_page_index = 1

            if field_page_index in field_groups:
                field_groups[field_page_index]["fields"].append(
                    {
                        "field_name": field_name,
                        "type": field_type,
                        "options": options,
                    }
                )

    def _determine_field_type(self, field_info):
        field_type = field_info.get("/FT", "text")
        if field_type == "/Btn":
            return "checkbox"
        if field_type == "/Ch":
            return "dropdown"
        if field_type == "/Tx":
            return "text"
        return field_type

    def _extract_field_options(self, field_info, reader):
        options = None

        if field_info.get("/FT") not in ["/Btn", "/Ch"]:
            return None

        kids = field_info.get("/Kids")
        if kids:
            options = self._extract_options_from_kids(kids, reader)
        elif field_info.get("/FT") == "/Ch" and "/Opt" in field_info:
            options = list(field_info.get("/Opt", []))

        return options

    def _extract_options_from_kids(self, kids, reader):
        options = []
        for kid in kids:
            kid_object = reader.get_object(kid)
            if not kid_object:
                continue

            ap = self._resolve_indirect_object(kid_object.get("/AP"), reader)
            if not isinstance(ap, dict) or "/N" not in ap:
                continue

            n_object = self._resolve_indirect_object(ap.get("/N"), reader)
            if not isinstance(n_object, dict):
                continue
            key_list = n_object.keys()
            keys = [k for k in key_list if k != "/Off"]
            options.extend(k.strip("/") for k in keys)

        return list(set(options)) if options else None

    def _resolve_indirect_object(self, obj, reader):
        if isinstance(obj, PyPDF2.generic.IndirectObject):
            return reader.get_object(obj)
        return obj

    def _format_extracted_data(self, field_groups):
        return [
            {"section_text": data["section_text"], "fields": data["fields"]}
            for data in field_groups.values()
            if data["fields"]
        ]
