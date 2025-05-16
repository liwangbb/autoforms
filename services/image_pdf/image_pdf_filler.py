import json
import os
import logging
from PIL import Image, ImageDraw, ImageFont
from pdf2image import convert_from_path
import PyPDF2
import fitz  # PyMuPDF
import statistics
import textwrap
import logging

logging.disable(logging.CRITICAL)

class ImagePDFfiller:
    """
    Class to fill PDF forms with answers from JSON data by drawing text on PDF images.
    This is intended to be used as the final step in a 3-step process:
    1. Extract questions from PDF to create a JSON file
    2. Add answers to the JSON file
    3. Fill the PDF with answers from the JSON file
    """
    
    def __init__(self, log_level=logging.INFO):
        """Initialize the ImagePDFfiller with logging configuration"""
        # Set up logging
        self.logger = logging.getLogger('ImagePDFfiller')
        self.logger.setLevel(log_level)
        
        # Create console handler if no handlers exist
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        self.logger.info("ImagePDFfiller initialized")
    
    def load_json_data(self, json_file):
        """Load the JSON data containing form field information"""
        self.logger.info(f"Loading JSON data from {json_file}")
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                self.logger.info(f"Successfully loaded JSON with {len(data)} fields")
                return data
        except Exception as e:
            self.logger.error(f"Failed to load JSON data: {e}")
            raise
    
    def analyze_pdf_text_sizes(self, pdf_path):
        """Analyze the PDF to extract typical text sizes used in form fields"""
        self.logger.info(f"Analyzing PDF text sizes in {pdf_path}")
        text_sizes = []
        
        try:
            # Open the PDF using PyMuPDF (fitz)
            doc = fitz.open(pdf_path)
            
            # Process each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text with formatting information
                text_instances = page.get_text("dict")["blocks"]
                
                # Extract font sizes from the text instances
                for block in text_instances:
                    if "lines" in block:
                        for line in block["lines"]:
                            if "spans" in line:
                                for span in line["spans"]:
                                    if "size" in span and span["size"] > 0:
                                        # Only consider reasonable form field text sizes (typically 8-14pt)
                                        if 6 <= span["size"] <= 16:
                                            text_sizes.append(span["size"])
            
            doc.close()
        except Exception as e:
            self.logger.warning(f"Could not analyze PDF text sizes using PyMuPDF: {e}")
        
        # If we found text sizes, calculate the median size for form fields
        if text_sizes:
            # Use median to avoid outliers
            median_size = statistics.median(text_sizes)
            # Most common sizes (mode)
            try:
                mode_size = statistics.mode(text_sizes)
                self.logger.info(f"Found {len(text_sizes)} text instances. Median size: {median_size}, Mode size: {mode_size}")
                return {"median": median_size, "mode": mode_size}
            except:
                self.logger.info(f"Found {len(text_sizes)} text instances. Median size: {median_size}")
                return {"median": median_size, "mode": median_size}
        
        # Default if analysis fails
        self.logger.warning("Could not determine text sizes, using default values")
        return {"median": 10, "mode": 10}  # Common form field size
    
    def estimate_dpi_scaling_factor(self, pdf_path):
        """Estimate the scaling factor between PDF points and image pixels at 300 DPI"""
        self.logger.info(f"Estimating DPI scaling factor for {pdf_path}")
        try:
            # Open the PDF using PyPDF2
            with open(pdf_path, 'rb') as file:
                pdf = PyPDF2.PdfReader(file)
                if len(pdf.pages) > 0:
                    # Get the first page
                    page = pdf.pages[0]
                    # Get the width and height in PDF points
                    pdf_width = float(page.mediabox.width)
                    pdf_height = float(page.mediabox.height)
                    
                    # Calculate the corresponding pixel dimensions at 300 DPI
                    # 1 point = 1/72 inch, so at 300 DPI that's 300/72 = 4.166... pixels per point
                    pixel_width = pdf_width * (300 / 72)
                    pixel_height = pdf_height * (300 / 72)
                    
                    scaling_factor = 300 / 72  # Pixels per point at 300 DPI
                    
                    self.logger.info(f"PDF dimensions: {pdf_width}x{pdf_height} points")
                    self.logger.info(f"Image dimensions at 300 DPI: {pixel_width:.1f}x{pixel_height:.1f} pixels")
                    self.logger.info(f"Scaling factor: {scaling_factor}")
                    
                    return {
                        "pdf_dimensions": (pdf_width, pdf_height),
                        "pixel_dimensions": (pixel_width, pixel_height),
                        "scaling_factor": scaling_factor
                    }
        except Exception as e:
            self.logger.warning(f"Could not calculate PDF scaling: {e}")
        
        # Default scaling factor for 300 DPI
        self.logger.warning("Using default scaling factor")
        return {"scaling_factor": 300 / 72}
    
    def find_usable_font(self, font_size):
        """Find a usable font for drawing text on the form"""
        # Try different fonts in order of preference
        font_options = [
            "Arial.ttf", 
            "Helvetica.ttf",
            "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
            "C:\\Windows\\Fonts\\arial.ttf",  # Windows
            "/Library/Fonts/Arial.ttf"  # macOS alternative
        ]
        
        for font_path in font_options:
            try:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, font_size)
                    self.logger.debug(f"Using font: {font_path} at size {font_size}")
                    return font
            except Exception as e:
                self.logger.debug(f"Could not use font {font_path}: {e}")
                continue
        
        # Fall back to default font if no others are available
        try:
            font = ImageFont.load_default()
            self.logger.warning("Using default font which may not match PDF text style")
            return font
        except Exception as e:
            self.logger.error(f"Could not load any font: {e}")
            return None
    
    def fill_pdf_with_answers(self, input_pdf, json_data, output_pdf, dpi=300):
        """Fill the PDF with answers at the specified coordinates with text starting from x1,y1"""
        self.logger.info(f"Starting to fill PDF {input_pdf} with form data")
        
        # First, analyze the PDF to get typical text sizes
        text_size_info = self.analyze_pdf_text_sizes(input_pdf)
        pdf_typical_font_size = text_size_info["mode"]  # Use the most common size
        
        # Get scaling information
        scaling_info = self.estimate_dpi_scaling_factor(input_pdf)
        scaling_factor = scaling_info["scaling_factor"]
        
        self.logger.info(f"PDF analysis: Typical font size = {pdf_typical_font_size}pt, Scaling factor = {scaling_factor}")
        
        # Convert PDF to images with higher DPI for better quality
        self.logger.info(f"Converting PDF to images at {dpi} DPI")
        try:
            images = convert_from_path(input_pdf, dpi=dpi)
            self.logger.info(f"PDF converted to {len(images)} image(s)")
        except Exception as e:
            self.logger.error(f"Failed to convert PDF to images: {e}")
            raise
        
        # Process each page
        for i, img in enumerate(images):
            # Get page dimensions
            width, height = img.size
            
            # Get fields for this page that need user input
            page_num = i + 1
            page_fields = [f for f in json_data if f.get('pageNumber') == page_num and f.get('needs_user_input') == True]
            
            self.logger.info(f"Processing page {page_num}: found {len(page_fields)} fields requiring input")
            
            if page_fields:
                draw = ImageDraw.Draw(img)
                
                # Draw each field's answer
                for field_idx, field in enumerate(page_fields):
                    try:
                        if 'answer_box_norm' in field and field['answer_box_norm'] is not None and 'questions' in field:
                            # Get coordinates from the normalized answer_box and convert to actual pixels
                            x1 = field['answer_box_norm']['x1'] * width
                            y1 = field['answer_box_norm']['y1'] * height
                            x2 = field['answer_box_norm']['x2'] * width
                            y2 = field['answer_box_norm']['y2'] * height
                            
                            # Calculate box dimensions
                            box_width = x2 - x1
                            box_height = y2 - y1
                            
                            field_id = field.get('id', f'unknown-{field_idx}')
                            self.logger.debug(f"Processing field ID: {field_id}, box: ({x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f})")
                            
                            answers_text = []
                            for question in field['questions']:
                                if "answers" in question and question["answers"]:
                                    answers_text.append(str(question["answers"]))
                            
                            if answers_text:
                                answer_text = ", ".join(answers_text)
                            else:
                                continue
                            
                            # IMPROVED FONT SIZE CALCULATION
                            # Start with the typical font size detected in the PDF, scaled to image resolution
                            base_font_size = pdf_typical_font_size * scaling_factor
                            
                            # Consider the field box height as a factor (using a smaller percentage for multiple lines)
                            line_height_factor = 0.6
                            box_based_size = box_height * line_height_factor
                            
                            # Take the smaller of the two sizes to ensure text fits
                            font_size = min(base_font_size, box_based_size)
                            
                            # Ensure font size is reasonable (scaled to image resolution)
                            min_font_size = 7 * scaling_factor  # Min size for readability
                            max_font_size = 14 * scaling_factor  # Slightly reduced max size for multiple lines
                            font_size = max(min_font_size, min(font_size, max_font_size))
                            
                            # Round to integer for font creation
                            font_size = int(font_size)
                            
                            self.logger.debug(f"Field {field_id}: Calculated font size {font_size} for answer: '{answer_text}'")
                            
                            # Find a suitable font
                            font = self.find_usable_font(font_size)
                            if font is None:
                                self.logger.error(f"Could not find a usable font for field {field_id}, skipping")
                                continue
                            
                            # Calculate average character width for this font
                            try:
                                # For Pillow >= 8.0.0
                                if hasattr(font, "getbbox"):
                                    sample_text = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                    sample_bbox = font.getbbox(sample_text)
                                    avg_char_width = (sample_bbox[2] - sample_bbox[0]) / len(sample_text)
                                else:
                                    # Fallback estimation
                                    avg_char_width = font_size * 0.55
                            except Exception as e:
                                self.logger.debug(f"Could not calculate character width: {e}, using estimation")
                                avg_char_width = font_size * 0.55
                            
                            # Calculate how many characters can fit in the box width with some padding
                            padding_factor = 0.95  # 5% padding on each side
                            usable_width = box_width * padding_factor
                            chars_per_line = max(1, int(usable_width / avg_char_width))
                            
                            # Calculate line height
                            line_height = font_size * 1.2
                            
                            # Set the starting position to exactly x1, y1 (top-left corner of the box)
                            text_x = x1
                            text_y = y1
                            
                            # Only wrap text if the box width exceeds 2/3 of the page width
                            should_wrap = box_width > (width * 2/3)
                            
                            if should_wrap and len(answer_text) > chars_per_line:
                                # Split the text into lines that fit within the box width
                                wrapped_lines = textwrap.wrap(answer_text, width=chars_per_line)
                                self.logger.debug(f"Field {field_id}: Text wrapped into {len(wrapped_lines)} lines")
                                
                                # Draw each line starting from the top-left (x1, y1)
                                current_y = text_y
                                for line in wrapped_lines:
                                    # Draw the line exactly at the current position
                                    draw.text((text_x, current_y), line, fill="black", font=font)
                                    current_y += line_height
                                    
                                    # Stop if we run out of space in the box
                                    if current_y >= y2:
                                        self.logger.warning(f"Field {field_id}: Not all text could fit in the box")
                                        break
                            else:
                                # For short text or narrow boxes, just start from x1, y1 without wrapping
                                draw.text((text_x, text_y), answer_text, fill="black", font=font)
                    except Exception as e:
                        self.logger.error(f"Error processing field {field_idx} on page {page_num}: {e}")
        
        # Save the modified images as a PDF with higher quality
        try:
            self.logger.info(f"Saving filled form as {output_pdf}")
            images[0].save(
                output_pdf, "PDF", resolution=dpi, save_all=True,
                append_images=images[1:]
            )
            self.logger.info(f"Form successfully filled and saved as {output_pdf}")
            return output_pdf
        except Exception as e:
            self.logger.error(f"Failed to save output PDF: {e}")
            raise
    
    def process(self, input_pdf, json_file, output_pdf, dpi=300):
        """Main processing function to fill a PDF with answers from a JSON file"""
        try:
            self.logger.info(f"Starting PDF filling process")
            self.logger.info(f"Input PDF: {input_pdf}")
            self.logger.info(f"JSON data: {json_file}")
            self.logger.info(f"Output PDF: {output_pdf}")
            
            # Load the JSON data
            data = self.load_json_data(json_file)
            
            # Fill the PDF with answers
            result = self.fill_pdf_with_answers(input_pdf, data, output_pdf, dpi)
            
            self.logger.info(f"Form filling completed successfully!")
            return result
        except Exception as e:
            self.logger.error(f"Form filling process failed: {e}")
            raise