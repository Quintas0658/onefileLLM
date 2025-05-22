from flask import Flask, request, jsonify
import os
import sys
import importlib.util

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import onefilellm module (we'll use functions directly)
import onefilellm
from onefilellm import crawl_and_extract_text

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "OneFileLLM API is running",
        "usage": "Send a POST request to /api/process with {'input_path': 'URL or file path', 'max_depth': 2}"
    })

@app.route('/api/process', methods=['POST'])
def process_api():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    input_path = data.get('input_path', '').strip()

    if not input_path:
        return jsonify({"error": "input_path is required"}), 400

    try:
        max_depth = int(data.get('max_depth', 2))
        
        # Call the appropriate processing function based on the input type
        final_output = None
        
        # Input type detection logic (similar to main() in onefilellm.py)
        if "github.com" in input_path:
            if "/pull/" in input_path:
                final_output = onefilellm.process_github_pull_request(input_path)
            elif "/issues/" in input_path:
                final_output = onefilellm.process_github_issue(input_path)
            else:  # Assume repository URL
                final_output = onefilellm.process_github_repo(input_path)
        elif onefilellm.urlparse(input_path).scheme in ["http", "https"]:
            if "youtube.com" in input_path or "youtu.be" in input_path:
                final_output = onefilellm.fetch_youtube_transcript(input_path)
            elif "arxiv.org/abs/" in input_path:
                final_output = onefilellm.process_arxiv_pdf(input_path)
            elif input_path.lower().endswith(('.pdf')):  # Direct PDF link
                crawl_result = onefilellm.crawl_and_extract_text(input_path, max_depth=0, include_pdfs=True, ignore_epubs=True)
                final_output = crawl_result['content']
            else:  # Assume general web URL for crawling
                crawl_result = onefilellm.crawl_and_extract_text(input_path, max_depth=max_depth, include_pdfs=True, ignore_epubs=True)
                final_output = crawl_result['content']
        # Basic check for DOI (starts with 10.) or PMID (all digits)
        elif (input_path.startswith("10.") and "/" in input_path) or input_path.isdigit():
            final_output = onefilellm.process_doi_or_pmid(input_path)
        elif os.path.isdir(input_path):  # Check if it's a local directory
            final_output = onefilellm.process_local_folder(input_path)
        elif os.path.isfile(input_path):  # Handle single local file
            relative_path = os.path.basename(input_path)
            file_content = onefilellm.safe_file_read(input_path)
            # Wrap single file in basic source/file XML
            final_output = (f'<source type="local_file" path="{onefilellm.escape_xml(input_path)}">\n'
                           f'<file path="{onefilellm.escape_xml(relative_path)}">\n'
                           f'{file_content}\n'
                           f'</file>\n'
                           f'</source>')
        else:  # Input not recognized
            return jsonify({"error": f"Input path or URL type not recognized: {input_path}"}), 400
            
        if final_output is None:
            return jsonify({"error": "Processing failed to produce any output"}), 500
            
        # Optionally strip XML tags if requested
        if data.get('strip_tags', False):
            # Since strip_xml_tags doesn't exist, create a simple version
            def strip_xml_tags(text):
                import re
                # Remove XML tags but keep content
                return re.sub(r'<[^>]+>', '', text)
            
            text_result = strip_xml_tags(final_output)
            return jsonify({"result": text_result, "format": "text"})
        
        return jsonify({"result": final_output, "format": "xml"})
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({"error": str(e), "traceback": error_trace}), 500

# For local development
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)

# For Heroku deployment
app_handler = app 