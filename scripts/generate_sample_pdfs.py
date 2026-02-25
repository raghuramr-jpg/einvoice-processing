"""Tool to generate sample PDF invoices from the text fixtures."""
import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def create_pdf(text_file_path: str, output_pdf_path: str):
    print(f"Generating {output_pdf_path} from {text_file_path}...")
    
    with open(text_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    c = canvas.Canvas(output_pdf_path, pagesize=A4)
    width, height = A4
    
    # 72 points per inch. Start near the top left
    x_margin = 50
    y_position = height - 50
    line_height = 14
    
    c.setFont("Courier", 10)
    
    for line in lines:
        line = line.rstrip('\n')
        c.drawString(x_margin, y_position, line)
        y_position -= line_height
        
        # Simple page break if we get too low
        if y_position < 50:
            c.showPage()
            c.setFont("Courier", 10)
            y_position = height - 50
    
    c.save()
    print(f"Created {output_pdf_path} successfully.")

if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent / "tests" / "sample_invoices"
    
    good_txt = base_dir / "sample_invoice.txt"
    bad_txt = base_dir / "bad_invoice.txt"
    
    good_pdf = base_dir / "sample_invoice.pdf"
    bad_pdf = base_dir / "bad_invoice.pdf"
    
    if good_txt.exists():
        create_pdf(str(good_txt), str(good_pdf))
    
    if bad_txt.exists():
        create_pdf(str(bad_txt), str(bad_pdf))
