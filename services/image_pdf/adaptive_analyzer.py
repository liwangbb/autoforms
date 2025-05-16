from collections import defaultdict
from typing import Dict, List, Tuple

import numpy as np


class AdaptiveFormAnalyzer:
    """
    An adaptive form analyzer that automatically learns form patterns and
    estimates answer boxes for form fields that require user input.

    Works with normalized coordinates (0-1) and can convert between normalized
    and absolute coordinates based on page dimensions.
    """

    def __init__(
        self,
        form_data: List[Dict],
        page_width: int = 612,
        page_height: int = 792,
    ):
        """
        Initialize the analyzer with form data.

        Args:
            form_data: List of dictionaries containing form elements with normalized coordinates
            page_width: Width of the page in points (default: 612 - standard US Letter width)
            page_height: Height of the page in points (default: 792 - standard US Letter height)
        """
        self.form_data = form_data
        self.page_width = page_width
        self.page_height = page_height

        # Organize data by page
        self.pages = self._organize_by_page()

        # Learn form structure automatically
        self.form_structure = self._learn_form_structure()

    def _organize_by_page(self) -> Dict:
        """Organize form elements by page number"""
        pages = {}

        for item in self.form_data:
            page = item.get("pageNumber", 1)
            if page not in pages:
                pages[page] = []

            # Set needs_user_input flag based on whether the item has questions
            item["needs_user_input"] = "questions" in item

            # No need to convert box format as the input already has the correct format
            # If question_box_norm exists, use that for layout sorting
            if "question_box_norm" in item:
                item["box"] = item["question_box_norm"]
            # Else fallback if nothing exists
            elif "label_box" in item:
                item["box"] = item["label_box"]
            else:
                item["box"] = {"x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.12}

            # Set label to text field if available
            if "text" in item and "label" not in item:
                item["label"] = item["text"]

            pages[page].append(item)

        # Sort items on each page (top to bottom, left to right)
        for page_num in pages:
            pages[page_num].sort(
                key=lambda x: (x["box"]["y1"], x["box"]["x1"])
            )

        return pages

    def _normalize_box(self, box: Dict, inverse: bool = False) -> Dict:
        """
        Convert between normalized (0-1) and absolute coordinates.

        Args:
            box: Dictionary with x1, y1, x2, y2 coordinates
            inverse: If True, convert from normalized to absolute, else absolute to normalized

        Returns:
            Dictionary with converted coordinates
        """
        if inverse:
            # Normalized to absolute
            return {
                "x1": box["x1"] * self.page_width,
                "y1": box["y1"] * self.page_height,
                "x2": box["x2"] * self.page_width,
                "y2": box["y2"] * self.page_height,
            }
        else:
            # Absolute to normalized
            return {
                "x1": box["x1"] / self.page_width,
                "y1": box["y1"] / self.page_height,
                "x2": box["x2"] / self.page_width,
                "y2": box["y2"] / self.page_height,
            }

    def _learn_form_structure(self) -> Dict:
        """
        Learn the structure of the form by analyzing patterns in the layout.
        Works with normalized coordinates to identify spacing and alignment patterns.
        """
        structure = {
            "form_width": 1.0,  # Normalized width
            "form_height": 1.0,  # Normalized height
            "avg_question_width": 0,
            "avg_question_height": 0,
            "avg_horizontal_gap": 0,
            "avg_vertical_gap": 0,
            "alignment_patterns": {},
            "column_structure": {},
        }

        # Collect width, height of all question boxes in normalized units
        widths = []
        heights = []

        # Collect horizontal and vertical gaps between consecutive elements
        horizontal_gaps = []
        vertical_gaps = []

        # Find alignment patterns and columns
        x_positions = defaultdict(int)
        y_positions = defaultdict(int)

        # Process each page
        for page_num, items in self.pages.items():
            # Collect box dimensions
            for item in items:
                box = item["box"]
                width = box["x2"] - box["x1"]
                height = box["y2"] - box["y1"]
                widths.append(width)
                heights.append(height)

                # Record x positions for column detection (bin into 20 segments)
                x_pos = round(box["x1"] * 20) / 20
                x_positions[x_pos] += 1

                # Record y positions for row detection (bin into 50 segments)
                y_pos = round(box["y1"] * 50) / 50
                y_positions[y_pos] += 1

            # Calculate gaps between elements
            for i in range(1, len(items)):
                curr = items[i]["box"]
                prev = items[i - 1]["box"]

                # If approximately on same row, calculate horizontal gap
                if abs(curr["y1"] - prev["y1"]) < 0.02:  # 2% of page height
                    h_gap = curr["x1"] - prev["x2"]
                    if h_gap > 0:
                        horizontal_gaps.append(h_gap)

                # If approximately in same column, calculate vertical gap
                if abs(curr["x1"] - prev["x1"]) < 0.02:  # 2% of page width
                    v_gap = curr["y1"] - prev["y2"]
                    if v_gap > 0:
                        vertical_gaps.append(v_gap)

        # Analyze collected data
        if widths:
            structure["avg_question_width"] = float(np.mean(widths))
            structure["min_question_width"] = float(np.min(widths))
            structure["max_question_width"] = float(np.max(widths))
        else:
            structure["avg_question_width"] = 0.2  # Default 20% of page width
            structure["min_question_width"] = 0.1  # Default 10% of page width
            structure["max_question_width"] = 0.3  # Default 30% of page width

        if heights:
            structure["avg_question_height"] = float(np.mean(heights))
            structure["min_question_height"] = float(np.min(heights))
            structure["max_question_height"] = float(np.max(heights))
        else:
            structure["avg_question_height"] = (
                0.03  # Default 3% of page height
            )
            structure["min_question_height"] = (
                0.02  # Default 2% of page height
            )
            structure["max_question_height"] = (
                0.05  # Default 5% of page height
            )

        if horizontal_gaps:
            # structure['avg_horizontal_gap'] = float(np.mean(horizontal_gaps))
            # # Minimum gap should be at least 1% of page width
            # structure['min_horizontal_gap'] = float(max(0.01, np.min(horizontal_gaps)))

            structure["avg_horizontal_gap"] = float(np.median(horizontal_gaps))
            structure["min_horizontal_gap"] = float(
                max(0.01, np.percentile(horizontal_gaps, 10))
            )
        else:
            structure["avg_horizontal_gap"] = 0.03  # Default 3% of page width
            structure["min_horizontal_gap"] = 0.01  # Default 1% of page width

        if vertical_gaps:
            # structure['avg_vertical_gap'] = float(np.mean(vertical_gaps))
            # # Minimum gap should be at least 0.5% of page height
            # structure['min_vertical_gap'] = float(max(0.005, np.min(vertical_gaps)))

            structure["avg_vertical_gap"] = float(
                np.median(vertical_gaps)
            )  # New (More robust)
            structure["min_vertical_gap"] = float(
                max(0.005, np.percentile(vertical_gaps, 10))
            )
        else:
            structure["avg_vertical_gap"] = 0.02  # Default 2% of page height
            structure["min_vertical_gap"] = (
                0.005  # Default 0.5% of page height
            )

        # Find potential columns (x positions that occur frequently)
        column_threshold = max(
            2, len(self.form_data) * 0.1
        )  # At least 10% of elements or 2 elements
        columns = sorted(
            [
                x
                for x, count in x_positions.items()
                if count >= column_threshold
            ]
        )
        structure["columns"] = columns

        # Find potential rows (y positions that occur frequently)
        row_threshold = max(2, len(self.form_data) * 0.1)
        rows = sorted(
            [y for y, count in y_positions.items() if count >= row_threshold]
        )
        structure["rows"] = rows

        return structure

    def _get_spatial_neighbors(
        self, item: Dict, page_items: List[Dict]
    ) -> Dict:
        """
        Find elements that are spatially adjacent to the current item.
        Works with normalized coordinates.
        """
        box = item["box"]
        x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]

        # Get typical spacing from learned form structure
        h_gap = self.form_structure["avg_horizontal_gap"]
        v_gap = self.form_structure["avg_vertical_gap"]

        # Adaptive thresholds based on form structure
        # Use a multiple of the average gaps to determine search distances
        # h_threshold = max(h_gap * 5, self.form_structure.get('max_question_width', 0.2))
        # v_threshold = max(v_gap * 5, self.form_structure.get('max_question_height', 0.05))
        h_threshold = max(
            h_gap * 4, self.form_structure.get("max_question_width", 0.2)
        )
        v_threshold = max(
            v_gap * 4, self.form_structure.get("max_question_height", 0.05)
        )

        right_neighbors = []
        below_neighbors = []

        for other in page_items:
            if other == item:
                continue

            other_box = other["box"]
            other_x1, other_y1 = other_box["x1"], other_box["y1"]
            other_x2, other_y2 = other_box["x2"], other_box["y2"]

            # To the right - horizontally adjacent and vertically aligned
            if (
                other_x1 > x2
                and abs((y1 + y2) / 2 - (other_y1 + other_y2) / 2)
                < v_threshold
                and other_x1 - x2 < h_threshold
            ):
                right_neighbors.append(
                    (other, other_x1 - x2)
                )  # Include distance

            # Below - vertically adjacent and horizontally aligned
            if (
                other_y1 > y2
                and abs((x1 + x2) / 2 - (other_x1 + other_x2) / 2)
                < h_threshold
                and other_y1 - y2 < v_threshold
            ):
                below_neighbors.append(
                    (other, other_y1 - y2)
                )  # Include distance

        # Sort by distance
        right_neighbors.sort(key=lambda n: n[1])
        below_neighbors.sort(key=lambda n: n[1])

        return {
            "right": [n[0] for n in right_neighbors],
            "below": [n[0] for n in below_neighbors],
        }

    def _determine_answer_placement(
        self, item: Dict, neighbors: Dict
    ) -> Tuple[str, Dict]:
        """
        Determine where to place the answer box and calculate its dimensions.
        Intelligently chooses between RIGHT and BELOW placement based on available space.
        Works with normalized coordinates.

        Args:
            item: Dictionary containing the question element
            neighbors: Dictionary of neighbors to the right and below

        Returns:
            Tuple of (placement_strategy, box_dimensions)
        """
        # Extract item information
        box = item["box"]

        # Get form dimensions and structure
        form_width = self.form_structure["form_width"]
        form_height = self.form_structure["form_height"]

        # Minimum reasonable width and height for an answer box based on form structure
        min_answer_width = min(
            self.form_structure.get("avg_question_width", 0.2),
            self.form_structure.get("min_question_width", 0.1),
        )

        min_answer_height = self.form_structure.get(
            "avg_question_height", 0.03
        )

        # Significantly reduce the minimum gaps
        h_gap = max(
            0.005, self.form_structure["min_horizontal_gap"] * 0.3
        )  # 30% of the minimum horizontal gap
        v_gap = max(
            0.003, self.form_structure["min_vertical_gap"] * 0.3
        )  # 30% of the minimum vertical gap

        # Check space to the right
        right_space = 0
        if not neighbors["right"]:
            # No neighbors to the right - space to page edge
            right_space = (
                form_width - box["x2"] - h_gap - 0.02
            )  # 2% margin from edge
        else:
            # Neighbor to the right - space to that element
            right_neighbor = neighbors["right"][0]
            right_space = right_neighbor["box"]["x1"] - box["x2"] - h_gap

        # Check space below
        below_space = 0
        if not neighbors["below"]:
            # No neighbors below - space to bottom of page
            below_space = (
                form_height - box["y2"] - v_gap - 0.02
            )  # 2% margin from bottom
        else:
            # Neighbor below - space to that element
            below_neighbor = neighbors["below"][0]
            below_space = below_neighbor["box"]["y1"] - box["y2"] - v_gap

        # Get question info and type
        question_text = item.get("label", "")
        question_length = len(question_text)
        is_long_question = question_length > 60

        # Default question type is text if not specified
        question_type = "text"

        # Extract the question type if available
        if "questions" in item and len(item["questions"]) > 0:
            question_type = item["questions"][0].get("type", "text")

        # Check if neighboring elements are too close (vertically)
        is_vertical_crowded = False
        if (
            neighbors["below"]
            and abs(neighbors["below"][0]["box"]["y1"] - box["y2"]) < 0.05
        ):  # Less than 5% of page height
            is_vertical_crowded = True

        # Check if neighboring elements are too close (horizontally)
        is_horizontal_crowded = False
        if (
            neighbors["right"]
            and abs(neighbors["right"][0]["box"]["x1"] - box["x2"]) < 0.1
        ):  # Less than 10% of page width
            is_horizontal_crowded = True

        # Force placements for specific question types or patterns
        force_placement = None

        # Process patterns in the form for specific placements
        # Force RIGHT placement for specific field types
        if (
            question_type in ["checkbox", "multiple_choice"]
            and not is_horizontal_crowded
        ):
            force_placement = "right"

        # Look for patterns like "field labels" that should place to the right
        # These often have short texts and appear on the left side of the form
        is_field_label = question_length < 25

        # Check for exact patterns that should have RIGHT placement
        if is_field_label:
            # Field labels like "Date:", "Name:", "Phone:" should place to the right
            # Make this very explicit with exact string matching for your specific form
            exact_right_fields = [
                "Date:",
                "Signature:",
                "Print Name:",
                "Phone Number:",
            ]
            if question_text in exact_right_fields or question_text.endswith(
                ":"
            ):
                # Very strong preference for right placement for these specific fields
                force_placement = "right"

        # Force BELOW placement for specific phrases and patterns
        # Check for exact patterns that should have BELOW placement
        below_patterns = [
            "Please provide copies",
            "Please indicate the primary",
            "Provide the current stage",
            "Describe the type and date",
            "If your patient's treatment",
            "Please outline the expected",
            "Please outline any additional",
            "Will your patient be left",
            "Canada Life supports",
            "Please provide any additional",
        ]

        if any(question_text.startswith(phrase) for phrase in below_patterns):
            force_placement = "below"

        # Q7 specific pattern detection - Force it to be below
        if "stage" in question_text.lower() or "TNM" in question_text:
            force_placement = "below"

        # Questions about cancer, stage, or surgical interventions tend to need more space
        medical_keywords = [
            "cancer",
            "stage",
            "tnm",
            "surgical",
            "treatment",
            "therapy",
            "condition",
            "prognosis",
            "outline",
            "describe",
            "provide",
        ]

        # Combine keyword check with length threshold
        if (
            any(
                keyword in question_text.lower()
                for keyword in medical_keywords
            )
            and question_length > 30
        ):
            force_placement = "below"

        # If we have a forced placement, use it
        if force_placement:
            if force_placement == "right":
                # RIGHT PLACEMENT (forced)
                # Use a minimum width even if space is limited
                # For fields like Date, Name, etc. - we'll use a small but functional width
                # if right_space <= 0:
                #     # If negative or zero space, use a minimal box and accept potential overlap
                #     right_width = max(0.05, min_answer_width)
                # else:
                #     right_width = min(right_space, 0.3)  # Limit to 30% of page width
                #     right_width = max(right_width, min(0.05, min_answer_width))  # Ensure minimum width

                # # For right placement, use similar height as the question box
                # box_height = box['y2'] - box['y1']

                # # Adjust height based on question type
                # if question_type == 'multiple_choice' or question_type == 'checkbox':
                #     box_height *= 1.2  # Make multiple choice boxes slightly taller

                # # Reduce the horizontal gap for right placement
                # adjusted_h_gap = min(h_gap, 0.01)  # Maximum 1% gap

                # return ('right', {
                #     'x1': box['x2'] + adjusted_h_gap,
                #     'y1': box['y1'],
                #     'x2': box['x2'] + adjusted_h_gap + right_width,
                #     'y2': box['y1'] + box_height
                # })
                if abs(right_space) > 0:
                    standard_width = 0.25
                    if item["label"] in [
                        "Date:",
                        "Signature:",
                        "Print Name:",
                        "Signature",
                    ]:
                        right_width = min(right_space, standard_width, 0.3)
                        right_width = max(right_width, 0.1)
                    else:
                        right_width = min(right_space, 0.3)
                        right_width = max(right_width, min_answer_width)

                    # Keep the height calculation
                    box_height = box["y2"] - box["y1"]
                    # Use a small gap
                    adjusted_h_gap = min(h_gap, 0.01)

                    # Calculate potential x2
                    potential_x2 = box["x2"] + adjusted_h_gap + right_width

                    # Prevent box going off-page (limit x2, e.g., to 0.98)
                    final_x2 = min(potential_x2, 0.98)

                    # Recalculate width in case it was clipped
                    right_width = final_x2 - (box["x2"] + adjusted_h_gap)

                    # Final check to ensure width is still usable
                    if right_width > 0.01:
                        # print(f"DEBUG: Applying RIGHT placement for: {item['label']} with width {right_width:.3f}") # Optional Debug
                        return (
                            "right",
                            {
                                "x1": box["x2"] + adjusted_h_gap,
                                "y1": box["y1"],
                                "x2": final_x2,
                                "y2": box["y1"] + box_height,
                            },
                        )

            elif (
                force_placement == "below"
                and below_space >= min_answer_height * 0.5
            ):
                # BELOW PLACEMENT (forced)
                # Allow smaller than minimum height if space is limited
                below_height = min(
                    0.15, below_space
                )  # Limit to 15% of page height
                below_height = max(
                    below_height, min(min_answer_height, 0.01)
                )  # Ensure minimum usable height

                # For below placement, use same width as question or slightly wider
                box_width = box["x2"] - box["x1"]
                if question_type == "text":
                    box_width = min(
                        0.8, box_width * 1.5
                    )  # Up to 80% of page width

                # Reduce the vertical gap for below placement
                adjusted_v_gap = min(v_gap, 0.005)  # Maximum 0.5% gap

                return (
                    "below",
                    {
                        "x1": box["x1"],
                        "y1": box["y2"] + adjusted_v_gap,
                        "x2": box["x1"] + box_width,
                        "y2": box["y2"] + adjusted_v_gap + below_height,
                    },
                )

        # If no force placement, calculate placement scores
        right_score = 1.0  # Default score
        if right_space > 0:
            right_score = right_space / max(
                0.01, min_answer_width
            )  # Avoid division by zero

        below_score = 1.0  # Default score
        if below_space > 0:
            below_score = below_space / max(
                0.01, min_answer_height
            )  # Avoid division by zero

        # Apply heuristic adjustments to scores
        # Spatial adjustments
        if below_space > 0.1:  # Good vertical space available
            below_score *= 1.2

        if right_space < 0.15:  # Limited horizontal space
            right_score *= 0.7

        # Question type and content adjustments
        if is_long_question:
            below_score *= 1.3  # Prefer below for complex questions

        # Type-based adjustments
        if question_type:
            if question_type in ["text"]:
                below_score *= 1.2  # Prefer below for text inputs
            elif question_type in ["multiple_choice", "checkbox"]:
                right_score *= 1.2  # Prefer right for choices
            elif question_type in ["date", "signature"]:
                right_score *= 1.5  # Strongly prefer right for these fields

        # Crowding adjustments
        if is_vertical_crowded:
            below_score *= 0.5  # Penalize below placement if crowded

        if is_horizontal_crowded:
            right_score *= 0.5  # Penalize right placement if crowded

        # For short field labels ending with colon, prefer right placement
        if is_field_label and question_text.endswith(":"):
            right_score *= 2.0  # Double the right score

        # Final placement decision
        use_below = (
            below_score > right_score
            and below_space >= min_answer_height * 0.5
        )

        # Create answer box based on chosen placement
        if not use_below:
            # RIGHT PLACEMENT
            # Use a reasonable width - not too wide, not too narrow
            # Handle negative or zero space
            if right_space <= 0:
                # If negative or zero space, use a minimal box and accept potential overlap
                right_width = max(0.05, min_answer_width)
            else:
                right_width = min(
                    right_space, 0.3
                )  # Limit to 30% of page width
                right_width = max(
                    right_width, min(0.05, min_answer_width)
                )  # Ensure minimum width

            # Keep the horizontal gap small
            adjusted_h_gap = min(h_gap, 0.01)  # Maximum 1% gap

            # For right placement, match the height of the question box
            box_height = box["y2"] - box["y1"]

            return (
                "right",
                {
                    "x1": box["x2"] + adjusted_h_gap,
                    "y1": box["y1"],
                    "x2": box["x2"] + adjusted_h_gap + right_width,
                    "y2": box["y1"] + box_height,
                },
            )

        else:
            # BELOW PLACEMENT
            # Calculate below answer box dimensions
            below_height = min(0.1, below_space)  # Limit to 10% of page height

            # Ensure minimum height, but allow smaller if space is limited
            below_height = max(below_height, min(min_answer_height, 0.01))

            # Keep the vertical gap very small
            adjusted_v_gap = min(v_gap, 0.005)  # Maximum 0.5% gap

            # Adjust width based on question type and content
            box_width = box["x2"] - box["x1"]
            if question_type == "text" and question_length > 30:
                # Make text boxes wider for longer questions
                box_width = min(
                    0.7, box_width * 1.5
                )  # Up to 70% of page width

            return (
                "below",
                {
                    "x1": box["x1"],
                    "y1": box["y2"] + adjusted_v_gap,
                    "x2": box["x1"] + box_width,
                    "y2": box["y2"] + adjusted_v_gap + below_height,
                },
            )

    def estimate_answer_boxes(self) -> List[Dict]:
        """
        Estimate answer boxes for all form elements that need user input.

        Returns:
            List of dictionaries with question and answer box information in normalized coordinates
        """
        results = []

        # Process each page
        for page_num, page_items in self.pages.items():
            for idx, item in enumerate(page_items):
                # Check if this element needs user input
                needs_input = item.get("needs_user_input", False)

                # Get question info if available
                questions = []
                if "questions" in item:
                    questions = item["questions"]

                # Only process elements that need user input
                if needs_input:
                    # Find spatial neighbors
                    neighbors = self._get_spatial_neighbors(item, page_items)

                    # Determine placement and calculate box dimensions
                    placement, answer_box = self._determine_answer_placement(
                        item, neighbors
                    )

                    # For visualization, convert to absolute coordinates
                    abs_question_box = self._normalize_box(
                        item["box"], inverse=True
                    )
                    abs_answer_box = (
                        self._normalize_box(answer_box, inverse=True)
                        if answer_box
                        else None
                    )
                else:
                    # Skip answer box creation for elements that don't need input
                    placement = "none"
                    answer_box = None
                    abs_question_box = self._normalize_box(
                        item["box"], inverse=True
                    )
                    abs_answer_box = None

                # Add to results (include all elements for completeness)
                result = {
                    "question_id": idx + 1,
                    "question": item.get("label", ""),
                    "question_box_norm": item["box"],
                    "question_box_abs": abs_question_box,
                    "answer_box_norm": answer_box,
                    "answer_box_abs": abs_answer_box,
                    "placement": placement,
                    "page": page_num,
                    "needs_user_input": needs_input,
                    "uid": item.get(
                        "uid", f"item_{idx+1}"
                    ),  # Use uid from input or generate one
                }

                # Include question type information if available
                if questions:
                    result["questions"] = questions

                results.append(result)

        return results
