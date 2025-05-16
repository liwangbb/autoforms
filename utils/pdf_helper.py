import os
import warnings
from typing import Any, Dict, List

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")


def is_digital_form_pdf(pdf_path: str) -> bool:
    try:
        reader = PdfReader(pdf_path)
        fields = reader.get_fields()
        return bool(fields)
    except PdfReadError as e:
        print(f"[PDF Detection Error] {e}")
        return False


def visualize(
    results: List[Dict],
    output_dir: str = ".",
    page_width: int = 612,
    page_height: int = 792,
) -> None:
    """
    Generate visualization of the form analysis.
    Uses absolute coordinates for visualization.

    Args:
        results: List of dictionaries containing question and answer box data.
        output_dir: Directory to save visualization images.
        page_width: Width of the page in points (default: 612 for US Letter).
        page_height: Height of the page in points (default: 792 for US Letter).
    """
    os.makedirs(output_dir, exist_ok=True)

    def _draw_item(ax, item: Dict):
        q_box = item["question_box_abs"]
        q_color = "green" if item.get("needs_user_input", False) else "blue"

        ax.add_patch(
            Rectangle(
                (q_box["x1"], q_box["y1"]),
                q_box["x2"] - q_box["x1"],
                q_box["y2"] - q_box["y1"],
                edgecolor=q_color,
                facecolor="none",
                linewidth=1,
            )
        )

        q_text = item.get("question", "")
        if len(q_text) > 40:
            q_text = q_text[:37] + "..."
        ax.text(
            q_box["x1"],
            q_box["y1"] - 5,
            f"{item.get('question_id', '?')}: {q_text}",
            fontsize=8,
            color=q_color,
        )

        if item.get("answer_box_abs"):
            a_box = item["answer_box_abs"]
            ax.add_patch(
                Rectangle(
                    (a_box["x1"], a_box["y1"]),
                    a_box["x2"] - a_box["x1"],
                    a_box["y2"] - a_box["y1"],
                    edgecolor="red",
                    facecolor="grey",
                    alpha=0.3,
                    linewidth=1,
                )
            )

            ax.text(
                a_box["x1"] + 5,
                a_box["y1"] + 10,
                item.get("placement", ""),
                fontsize=6,
                color="red",
            )

            if item["placement"] == "right":
                ax.plot(
                    [q_box["x2"], a_box["x1"]],
                    [
                        (q_box["y1"] + q_box["y2"]) / 2,
                        (a_box["y1"] + a_box["y2"]) / 2,
                    ],
                    "r--",
                    linewidth=0.5,
                )
            elif item["placement"] == "below":
                ax.plot(
                    [
                        (q_box["x1"] + q_box["x2"]) / 2,
                        (a_box["x1"] + a_box["x2"]) / 2,
                    ],
                    [q_box["y2"], a_box["y1"]],
                    "r--",
                    linewidth=0.5,
                )

    # Group by page
    by_page = {}
    for item in results:
        page = item["page"]
        by_page.setdefault(page, []).append(item)

    for page_num, page_items in by_page.items():
        _, ax = plt.subplots(figsize=(8.5, 11))  # US Letter size
        ax.set_xlim(0, page_width)
        ax.set_ylim(page_height, 0)  # Inverted y-axis

        for item in page_items:
            _draw_item(ax, item)

        plt.title(f"Form Analysis - Page {page_num}")
        output_file = os.path.join(
            output_dir, f"form_analysis_page{page_num}.png"
        )
        plt.savefig(output_file, dpi=300)
        plt.close()
        print(f"Visualization saved to {output_file}")


def package_pipeline_output(
    questions: List[Dict[str, Any]],
    summary: str,
    answers: List[Dict[str, Any]],
    fill_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "questions": questions,
        "summary": summary,
        "answers": answers,
        **fill_result,
    }
