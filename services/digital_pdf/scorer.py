"""
Module: scorer.py
This module provides functionality to score and match PDF form fields to their
respective pages using various scoring techniques.
"""

import re
from difflib import SequenceMatcher


class FieldScorer:
    def __init__(self):
        pass

    def field_page_detection(self, field_name, field_groups, options=None):
        """
        Detects which page a field belongs to by scoring each page.

        Args:
            field_name (str): The name of the field to locate
            field_groups (dict): Dictionary of page data with visible text
            options (list, optional): List of field options to consider

        Returns:
            int: The page number where the field most likely belongs
        """
        matches = self._score_pages_for_field(
            field_name,
            field_groups,
            options,
        )

        if matches:
            return max(matches.items(), key=lambda x: x[1])[0]

        return self._find_best_fuzzy_match(field_name, field_groups)

    def score_text_similarity(self, text1, text2):
        """
        Calculate similarity score between two text strings.

        Args:
            text1 (str): First text string
            text2 (str): Second text string

        Returns:
            float: Similarity score between 0 and 1
        """
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def _generate_field_variations(self, field_name):
        return [
            field_name,
            field_name.lower(),
            field_name.upper(),
            field_name.title(),
            field_name.replace("_", " "),
            field_name.replace("-", " "),
            re.sub(r"^field_", "", field_name, flags=re.IGNORECASE),
            re.sub(r"^input_", "", field_name, flags=re.IGNORECASE),
        ]

    def _generate_label_patterns(self, variations):
        patterns = []
        for variation in variations:
            patterns.extend(
                [
                    f"{variation}:",
                    f"{variation} *",
                    f"{variation}*",
                    f"{variation} (",
                    f"*{variation}*",
                    f"*{variation}",
                    f"{variation}*",
                    f'"{variation}"',
                    f"'{variation}'",
                ]
            )
        return patterns

    def _score_pages_for_field(self, field_name, field_groups, options=None):
        matches = {}

        for page_num, data in field_groups.items():
            score = self._calculate_page_score(
                field_name,
                data["visible_text"],
            )
            matches[page_num] = score

        if options and isinstance(options, list):
            self._add_option_based_scores(field_groups, options, matches)

        return matches

    def _calculate_page_score(self, field_name, text_blocks):
        variations = self._generate_field_variations(field_name)
        label_patterns = self._generate_label_patterns(variations)
        proximity_indicators = self._get_proximity_indicators()

        page_score = 0

        for text_block in text_blocks:
            text_lower = text_block.lower()
            field_lower = field_name.lower()

            page_score += self._score_variations(variations, text_lower)
            page_score += self._score_patterns(label_patterns, text_lower)
            page_score += self._score_proximity(
                proximity_indicators, text_lower, field_lower
            )
            page_score += self._score_context(text_lower, field_lower)
            page_score += self._score_similarity(text_lower, field_lower)
            page_score += self._score_subwords(field_name, text_lower)

        return page_score

    def _score_subwords(self, field_name, text_lower):
        score = 0
        field_lower = field_name.lower()

        subwords = {field_lower}
        for delimiter in ["_", "-", "/", " "]:
            subwords |= {
                word for part in subwords for word in part.split(delimiter)
            }

        camel_case_text = re.sub(
            r"([a-z])([A-Z])", r"\1 \2", field_name
        ).lower()
        subwords |= set(camel_case_text.split())

        stopwords = {
            "the",
            "and",
            "for",
            "of",
            "or",
            "to",
            "in",
            "on",
            "at",
            "by",
        }
        meaningful_subwords = {
            word
            for word in subwords
            if len(word) > 2 and word not in stopwords
        }

        score += sum(
            min(len(subword), 5)
            for subword in meaningful_subwords
            if subword in text_lower
        )

        return score

    def _get_proximity_indicators(self):
        return [
            "enter",
            "provide",
            "fill",
            "input",
            "required",
            "optional",
            "please",
            "select",
            "choose",
            "specify",
            "indicate",
        ]

    def _score_variations(self, variations, text_lower):
        score = 0
        for variation in variations:
            if variation.lower() in text_lower:
                score += 5
        return score

    def _score_patterns(self, patterns, text_lower):
        score = 0
        for pattern in patterns:
            if pattern.lower() in text_lower:
                score += 8
        return score

    def _score_proximity(self, indicators, text_lower, field_lower):
        score = 0
        for indicator in indicators:
            if indicator in text_lower and field_lower in text_lower:
                score += 3
        return score

    def _score_context(self, text_lower, field_lower):
        words = text_lower.split()
        if len(words) > 5 and field_lower in text_lower:
            return 2
        return 0

    def _score_similarity(self, text_lower, field_lower):
        similarity = SequenceMatcher(None, field_lower, text_lower).ratio()
        if similarity > 0.8:
            return int(similarity * 10)
        return 0

    def _add_option_based_scores(self, field_groups, options, matches):
        for page_num, data in field_groups.items():
            page_text = " ".join(data["visible_text"]).lower()
            options_found = 0

            for option in options:
                if isinstance(option, str) and option.lower() in page_text:
                    options_found += 1

            if options_found > 1:
                matches.setdefault(page_num, 0)
                matches[page_num] += options_found * 10
            elif options_found == 1:
                matches[page_num] = matches.get(page_num, 0) + 5

    def _find_best_fuzzy_match(self, field_name, field_groups):
        best_match = None
        best_score = 0

        for page_num, data in field_groups.items():
            for text_block in data["visible_text"]:
                similarity = SequenceMatcher(
                    None, field_name.lower(), text_block.lower()
                ).ratio()
                if similarity > best_score:
                    best_score = similarity
                    best_match = page_num

        return best_match
