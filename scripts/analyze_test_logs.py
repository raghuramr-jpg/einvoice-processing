import re

def analyze_logs(file_path):
    with open(file_path, 'r', encoding='utf-16le') as f:
        content = f.read()
    
    # Look for the debug prints
    node_start = re.search(r"CRITICAL DEBUG: ingestion_node STARTED", content)
    if node_start:
        print("--- Node Start Found ---")
    
    ocr_debug = re.search(r"DEBUG: Fallback OCR extracted (.*)", content)
    if ocr_debug:
        print(f"OCR Debug: {ocr_debug.group(1)[:200]}...")
    
    text_llm_debug = re.search(r"DEBUG: Text LLM raw result: (.*)", content)
    if text_llm_debug:
        print(f"Text LLM Raw Result (first 500 chars): {text_llm_debug.group(1)[:500]}...")
    
    final_data_debug = re.search(r"DEBUG: Final extracted data: (.*)", content)
    if final_data_debug:
        print(f"Final Data Debug: {final_data_debug.group(1)}")

if __name__ == "__main__":
    analyze_logs("test_debug_output.txt")
