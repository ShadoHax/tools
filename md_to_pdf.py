#!/usr/bin/env python3
"""
Markdown to PDF Converter with MathJax Support
Converts markdown files with LaTeX math equations to PDF with custom fonts.

Usage:
    python md_to_pdf.py input.md [output.pdf] [font_url] [--no-open]
    
Arguments:
    input.md    - Input markdown file
    output.pdf  - (Optional) Output PDF filename. Defaults to input name with .pdf extension
    font_url    - (Optional) Google Fonts CSS URL. Defaults to Nunito Sans
    --no-open   - (Optional) Don't automatically open the PDF after creation
    
Examples:
    python md_to_pdf.py study_guide.md
    python md_to_pdf.py study_guide.md my_output.pdf
    python md_to_pdf.py study_guide.md output.pdf "https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600;700&display=swap"
    python md_to_pdf.py study_guide.md --no-open

Features:
    - LaTeX math equations (inline: $...$, display: $$...$$)
    - Headers (h1-h6): #, ##, ###, ####, #####, ######
    - Bold, italic, strikethrough
    - Links and images
    - Unordered and ordered lists
    - Task lists: - [ ] and - [x]
    - Code blocks and inline code
    - Blockquotes
    - Horizontal rules
    - Automatic filename collision avoidance with (1), (2), etc.
"""

import sys
import os
from pathlib import Path
import re
import argparse
from urllib.parse import urlparse, parse_qs
import platform
import subprocess
import html as html_lib


def generate_header_id(header_text):
    """Generate a URL-friendly ID from header text, matching GitHub markdown style."""
    # Remove markdown formatting
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'\1', header_text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Convert to lowercase
    text = text.lower()
    
    # Replace spaces and special chars with hyphens
    text = re.sub(r'[^\w\s-]', '', text)  # Remove special chars except spaces and hyphens
    text = re.sub(r'[-\s]+', '-', text)    # Replace spaces and multiple hyphens with single hyphen
    text = text.strip('-')                  # Remove leading/trailing hyphens
    
    return text


def extract_font_family(font_url):
    """Extract the font family name from a Google Fonts URL."""
    try:
        # Parse URL like: https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@200..1000&display=swap
        parsed = urlparse(font_url)
        query = parse_qs(parsed.query)
        
        if 'family' in query:
            family = query['family'][0]
            # Remove weight/style specifications (everything after ':')
            family = family.split(':')[0]
            # Replace + with spaces
            family = family.replace('+', ' ')
            return family
    except:
        pass
    
    return "Nunito Sans"

    """Extract the font family name from a Google Fonts URL."""
    try:
        # Parse URL like: https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@200..1000&display=swap
        parsed = urlparse(font_url)
        query = parse_qs(parsed.query)
        
        if 'family' in query:
            family = query['family'][0]
            # Remove weight/style specifications (everything after ':')
            family = family.split(':')[0]
            # Replace + with spaces
            family = family.replace('+', ' ')
            return family
    except:
        pass
    
    return "Nunito Sans"


def strip_markdown_formatting(text):
    """Remove lightweight markdown formatting from heading text."""
    text = re.sub(r'!\[([^\]]*)\]\(([^\)]+)\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'\1', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'(?<!\*)\*(?!\s)(.*?)(?<!\s)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<!_)_(?!\s)(.*?)(?<!\s)_(?!_)', r'\1', text)
    text = re.sub(r'~~(.*?)~~', r'\1', text)
    text = text.replace('\\\\', '\\')
    return html_lib.unescape(text).strip()


def extract_markdown_headings(markdown_content):
    """Extract ATX headings (#, ##, etc.) from markdown for PDF bookmarks."""
    headings = []
    in_fenced_code = False

    for line in markdown_content.splitlines():
        stripped = line.strip()

        if re.match(r'^(```|~~~)', stripped):
            in_fenced_code = not in_fenced_code
            continue

        if in_fenced_code:
            continue

        match = re.match(r'^(#{1,6})\s+(.*?)(?:\s+#+\s*)?$', stripped)
        if not match:
            continue

        level = len(match.group(1))
        raw_text = match.group(2).strip()
        clean_text = strip_markdown_formatting(raw_text)
        if clean_text:
            headings.append({
                'level': level,
                'text': clean_text,
                'id': generate_header_id(clean_text),
            })

    return headings


def add_pdf_bookmarks(pdf_path, headings):
    """Add a real PDF bookmark tree by locating heading text in the rendered PDF."""
    if not headings:
        return False, 'No markdown headings found; skipped bookmark generation.'

    try:
        import fitz
    except ImportError:
        return False, 'PyMuPDF (fitz) is not installed; skipped bookmark generation.'

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        return False, f'Could not open generated PDF for bookmark pass: {exc}'

    toc = []
    search_start_page = 0

    def normalize_spaces(value):
        return re.sub(r'\s+', ' ', value).strip()

    try:
        for heading in headings:
            target = normalize_spaces(heading['text'])
            found_page = None

            for page_index in range(search_start_page, len(doc)):
                page = doc[page_index]
                page_text = normalize_spaces(page.get_text('text'))
                if target in page_text:
                    found_page = page_index
                    search_start_page = page_index
                    break

            if found_page is None:
                for page_index in range(0, search_start_page):
                    page = doc[page_index]
                    page_text = normalize_spaces(page.get_text('text'))
                    if target in page_text:
                        found_page = page_index
                        break

            if found_page is not None:
                toc.append([heading['level'], heading['text'], found_page + 1])

        if not toc:
            doc.close()
            return False, 'Rendered PDF text did not contain any detectable heading strings.'

        doc.set_toc(toc)
        doc.save(str(pdf_path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        doc.close()
        return True, f'Embedded {len(toc)} PDF bookmarks from markdown headings.'
    except Exception as exc:
        try:
            doc.close()
        except Exception:
            pass
        return False, f'Bookmark post-processing failed: {exc}'


def markdown_to_html(markdown_content, font_url, font_family):
    """Convert markdown to HTML with MathJax support and custom fonts."""
    
    # Simple markdown to HTML conversion
    html = markdown_content
    
    # --- Protect math and code expressions from markdown formatting ---
    # Extract display math ($$...$$), inline math ($...$), and code blocks/inline
    # first, replacing them with unique placeholders. Restored at the end.
    math_store = {}
    math_counter = [0]

    def stash(content):
        key = f'\x00MATH{math_counter[0]}\x00'
        math_store[key] = content
        math_counter[0] += 1
        return key

    # Code blocks first (``` ... ```) — must come before inline code/math
    html = re.sub(
        r'```(\w*)\n(.*?)```',
        lambda m: stash(f'```{m.group(1)}\n{m.group(2)}```'),
        html,
        flags=re.DOTALL
    )
    # Inline code
    html = re.sub(r'`([^`]+)`', lambda m: stash(f'`{m.group(1)}`'), html)
    # Display math $$...$$
    html = re.sub(r'\$\$(.*?)\$\$', lambda m: stash(f'$${m.group(1)}$$'), html, flags=re.DOTALL)
    # Inline math $...$
    html = re.sub(r'\$([^\$\n]+?)\$', lambda m: stash(f'${m.group(1)}$'), html)

    # Convert headers (process from most specific to least specific)
    # First, capture headers and add IDs
    def add_header_id(match):
        level = len(match.group(1))
        text = match.group(2)
        header_id = generate_header_id(text)
        return f'<h{level} id="{header_id}">{text}</h{level}>'
    
    html = re.sub(r'^(#{1,6})\s+(.*?)$', add_header_id, html, flags=re.MULTILINE)
    
    # Convert strikethrough
    html = re.sub(r'~~(.*?)~~', r'<del>\1</del>', html)
    
    # Convert bold and italic
    html = re.sub(r'\*\*\*(.*?)\*\*\*', r'<strong><em>\1</em></strong>', html)
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    
    # Convert links [text](url)
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)
    
    # Convert images ![alt](url)
    html = re.sub(r'!\[([^\]]*)\]\(([^\)]+)\)', r'<img src="\2" alt="\1" />', html)
    
    # --- Restore stashed math and code, now converting them to their HTML forms ---
    def restore(text):
        for key, original in math_store.items():
            if original.startswith('```'):
                # Code block
                converted = re.sub(
                    r'```(\w*)\n(.*?)```',
                    r'<pre><code class="language-\1">\2</code></pre>',
                    original,
                    flags=re.DOTALL
                )
                text = text.replace(key, converted)
            elif original.startswith('`'):
                # Inline code
                converted = re.sub(r'`([^`]+)`', r'<code>\1</code>', original)
                text = text.replace(key, converted)
            else:
                # Math — pass through as-is for MathJax
                text = text.replace(key, original)
        return text

    # Unescape markdown escape sequences (e.g. \_ -> _, \* -> *, etc.)
    # Must happen BEFORE restore so math placeholders (still stashed) are not affected.
    # If this ran after restore, \\ in LaTeX matrix row-separators would be stripped
    # down to \ and all rows would collapse onto one line.
    html = re.sub(r'\\([_*`~\\#\[\](){}+\-!|])', r'\1', html)

    html = restore(html)
    
    # Convert horizontal rules
    html = re.sub(r'^---$', r'<hr>', html, flags=re.MULTILINE)
    html = re.sub(r'^\*\*\*$', r'<hr>', html, flags=re.MULTILINE)
    
    # Convert blockquotes (lines starting with >)
    lines = html.split('\n')
    in_blockquote = False
    in_list = False
    in_ordered_list = False
    result_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Handle tables
        if stripped.startswith('|') and stripped.endswith('|'):
            # Check if the next line is a separator row (e.g. |---|---|)
            next_stripped = lines[i + 1].strip() if i + 1 < len(lines) else ''
            if re.match(r'^\|[\s\-:|]+\|$', next_stripped):
                table_html = ['<table>']
                # Header row
                headers = [cell.strip() for cell in stripped[1:-1].split('|')]
                table_html.append('<thead><tr>')
                for h in headers:
                    table_html.append(f'<th>{h}</th>')
                table_html.append('</tr></thead>')
                i += 2  # skip header row and separator row
                # Body rows
                table_html.append('<tbody>')
                while i < len(lines):
                    row = lines[i].strip()
                    if row.startswith('|') and row.endswith('|'):
                        cells = [cell.strip() for cell in row[1:-1].split('|')]
                        table_html.append('<tr>')
                        for cell in cells:
                            table_html.append(f'<td>{cell}</td>')
                        table_html.append('</tr>')
                        i += 1
                    else:
                        break
                table_html.append('</tbody></table>')
                result_lines.append('\n'.join(table_html))
                continue

        # Handle blockquotes
        if stripped.startswith('>'):
            if not in_blockquote:
                result_lines.append('<blockquote>')
                in_blockquote = True
            result_lines.append('<p>' + stripped[1:].strip() + '</p>')
            i += 1
            continue
        else:
            if in_blockquote:
                result_lines.append('</blockquote>')
                in_blockquote = False
        
        # Handle unordered lists (-, *, +)
        if re.match(r'^[\*\-\+]\s+', stripped):
            if not in_list:
                result_lines.append('<ul>')
                in_list = True
            # Handle task lists
            task_match = re.match(r'^[\*\-\+]\s+\[([ xX])\]\s+(.*)', stripped)
            if task_match:
                checked = 'checked' if task_match.group(1).lower() == 'x' else ''
                result_lines.append(f'<li><input type="checkbox" {checked} disabled> {task_match.group(2)}</li>')
            else:
                result_lines.append('<li>' + re.sub(r'^[\*\-\+]\s+', '', stripped) + '</li>')
            i += 1
            continue
        elif not stripped and in_list:
            # Blank line — look ahead to see if another unordered list item follows
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and re.match(r'^[\*\-\+]\s+', lines[j].strip()):
                i += 1  # skip blank line, stay in list
                continue
            else:
                result_lines.append('</ul>')
                in_list = False
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
        
        # Handle ordered lists (1. 2. etc.)
        if re.match(r'^\d+\.\s+', stripped):
            if not in_ordered_list:
                result_lines.append('<ol>')
                in_ordered_list = True
            result_lines.append('<li>' + re.sub(r'^\d+\.\s+', '', stripped) + '</li>')
            i += 1
            continue
        elif not stripped and in_ordered_list:
            # Blank line — look ahead to see if another ordered list item follows
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and re.match(r'^\d+\.\s+', lines[j].strip()):
                i += 1  # skip blank line, stay in list
                continue
            else:
                result_lines.append('</ol>')
                in_ordered_list = False
        else:
            if in_ordered_list:
                result_lines.append('</ol>')
                in_ordered_list = False
        
        result_lines.append(line)
        i += 1
    
    # Close any open lists or blockquotes
    if in_blockquote:
        result_lines.append('</blockquote>')
    if in_list:
        result_lines.append('</ul>')
    if in_ordered_list:
        result_lines.append('</ol>')
    
    html = '\n'.join(result_lines)
    
    # Convert paragraphs (simple version)
    html = re.sub(r'\n\n', r'</p><p>', html)
    html = '<p>' + html + '</p>'
    
    # Clean up empty paragraphs
    html = re.sub(r'<p>\s*</p>', '', html)
    html = re.sub(r'<p>\s*<h([1-6])>', r'<h\1>', html)
    html = re.sub(r'</h([1-6])>\s*</p>', r'</h\1>', html)
    html = re.sub(r'<p>\s*<hr>', r'<hr>', html)
    html = re.sub(r'</p>\s*<hr>', r'<hr>', html)
    html = re.sub(r'<p>\s*<(ul|ol|blockquote|pre|table)>', r'<\1>', html)
    html = re.sub(r'</(ul|ol|blockquote|pre|table)>\s*</p>', r'</\1>', html)
    
    # Wrap in full HTML document
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Study Guide</title>
    
    <!-- Google Fonts -->
    <link href="{font_url}" rel="stylesheet">
    
    <!-- MathJax Configuration -->
    <script>
        MathJax = {{
            tex: {{
                inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
                processEscapes: true,
                processEnvironments: true
            }},
            options: {{
                skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
            }}
        }};
    </script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" async></script>
    
    <style>
        @page {{
            size: letter;
            margin: 0.75in;
        }}
        
        body {{
            font-family: '{font_family}', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 100%;
            margin: 0;
            padding: 0;
            font-size: 11pt;
            scroll-behavior: smooth;
        }}
        
        h1 {{
            font-size: 24pt;
            font-weight: 700;
            margin-top: 24pt;
            margin-bottom: 12pt;
            color: #1a1a1a;
            page-break-after: avoid;
        }}
        
        h2 {{
            font-size: 18pt;
            font-weight: 600;
            margin-top: 18pt;
            margin-bottom: 10pt;
            color: #2c3e50;
            page-break-after: avoid;
            border-bottom: 2px solid #e1e4e8;
            padding-bottom: 6pt;
        }}
        
        h3 {{
            font-size: 14pt;
            font-weight: 600;
            margin-top: 14pt;
            margin-bottom: 8pt;
            color: #34495e;
            page-break-after: avoid;
        }}
        
        h4 {{
            font-size: 12pt;
            font-weight: 600;
            margin-top: 12pt;
            margin-bottom: 6pt;
            color: #34495e;
        }}
        
        h5 {{
            font-size: 11pt;
            font-weight: 600;
            margin-top: 10pt;
            margin-bottom: 5pt;
            color: #34495e;
        }}
        
        h6 {{
            font-size: 10pt;
            font-weight: 600;
            margin-top: 8pt;
            margin-bottom: 4pt;
            color: #34495e;
        }}
        
        p {{
            margin-top: 0;
            margin-bottom: 10pt;
            text-align: justify;
        }}
        
        strong {{
            font-weight: 600;
        }}
        
        em {{
            font-style: italic;
            padding-right: 0.15em;
            margin-right: -0.15em;
        }}
        
        del {{
            text-decoration: line-through;
            color: #666;
        }}
        
        a {{
            color: #3498db;
            text-decoration: underline;
        }}
        
        a:hover {{
            text-decoration: underline;
            color: #2980b9;
        }}
        
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 12pt auto;
        }}
        
        code {{
            font-family: 'Courier New', Courier, monospace;
            background-color: #f6f8fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        
        pre {{
            background-color: #f6f8fa;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 12pt;
            margin: 12pt 0;
            overflow-x: auto;
            page-break-inside: avoid;
        }}
        
        pre code {{
            background-color: transparent;
            padding: 0;
            font-size: 0.85em;
            line-height: 1.45;
        }}
        
        blockquote {{
            border-left: 4px solid #3498db;
            background-color: #f0f8ff;
            padding: 10pt 15pt;
            margin: 12pt 0;
            page-break-inside: avoid;
        }}
        
        blockquote p {{
            margin: 6pt 0;
        }}
        
        hr {{
            border: none;
            border-top: 2px solid #e1e4e8;
            margin: 18pt 0;
        }}
        
        ul, ol {{
            margin: 8pt 0;
            padding-left: 30pt;
        }}
        
        li {{
            margin: 4pt 0;
        }}
        
        ul ul, ol ol, ul ol, ol ul {{
            margin: 4pt 0;
        }}
        
        input[type="checkbox"] {{
            margin-right: 6pt;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 12pt 0;
            font-size: 10pt;
        }}
        
        th, td {{
            border: 1px solid #ddd;
            padding: 8pt;
            text-align: left;
        }}
        
        th {{
            background-color: #f6f8fa;
            font-weight: 600;
        }}
        
        /* Math styling */
        mjx-container {{
            margin: 8pt 0;
        }}
        
        mjx-container[display="true"] {{
            margin: 12pt 0;
        }}
        
        /* Page break control */
        h1, h2, h3, h4, h5, h6 {{
            page-break-after: avoid;
        }}

        /* Explicit PDF bookmark hierarchy for renderers that honor it */
        h1 {{ bookmark-level: 1; }}
        h2 {{ bookmark-level: 2; }}
        h3 {{ bookmark-level: 3; }}
        h4 {{ bookmark-level: 4; }}
        h5 {{ bookmark-level: 5; }}
        h6 {{ bookmark-level: 6; }}
        
        .page-break {{
            page-break-before: always;
        }}
        
        /* Print optimizations */
        @media print {{
            body {{
                font-size: 11pt;
            }}
            
            h1 {{
                font-size: 22pt;
            }}
            
            h2 {{
                font-size: 17pt;
            }}
            
            h3 {{
                font-size: 13pt;
            }}
            
            a {{
                color: #3498db;
                text-decoration: underline;
            }}
        }}
    </style>
</head>
<body>
    {html}
</body>
</html>"""
    
    return html_doc


def open_file(filepath):
    """Open a file with the default application without stealing focus."""
    try:
        system = platform.system()
        if system == 'Windows':
            # Use START command with /B to open without stealing focus
            subprocess.Popen(['cmd', '/c', 'start', '/B', '', filepath], 
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        elif system == 'Darwin':  # macOS
            # Use -g flag to open in background
            subprocess.Popen(['open', '-g', filepath])
        else:  # Linux and others
            # xdg-open typically doesn't steal focus, but we can detach it
            subprocess.Popen(['xdg-open', filepath], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"Could not open file automatically: {e}", file=sys.stderr)
        return False


def convert_to_pdf(input_file, output_file=None, font_url=None, auto_open=True):
    """Convert markdown file to PDF."""
    
    # Default font URL (Nunito Sans)
    if font_url is None:
        font_url = "https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@200..1000&display=swap"
    
    # Extract font family name
    font_family = extract_font_family(font_url)
    
    # Determine input and output paths
    input_path = Path(input_file).resolve()
    
    if not input_path.exists():
        print(f"Error: Input file '{input_file}' not found.", file=sys.stderr)
        return 1
    
    # Determine output path
    if output_file is None:
        output_path = input_path.with_suffix('.pdf')
    else:
        output_path = Path(output_file)
        # If output_file is just a filename, put it in the same directory as input
        if not output_path.is_absolute():
            output_path = input_path.parent / output_path
        if output_path.suffix != '.pdf':
            output_path = output_path.with_suffix('.pdf')
    
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print(f"Font:   {font_family}")
    
    # Check if output file exists and prompt for overwrite
    if output_path.exists():
        while True:
            response = input(f"\nFile '{output_path}' already exists. Overwrite? (Y)es/(N)o: ").strip().lower()
            if response in ['y', 'yes']:
                print("Overwriting existing file...")
                break
            elif response in ['n', 'no']:
                # Find next available filename with (1), (2), etc.
                base_path = output_path.parent / output_path.stem
                ext = output_path.suffix
                counter = 1
                while True:
                    new_path = output_path.parent / f"{output_path.stem} ({counter}){ext}"
                    if not new_path.exists():
                        output_path = new_path
                        print(f"Using alternative filename: {output_path.name}")
                        break
                    counter += 1
                break
            else:
                print("Please enter 'Y' or 'N'.")
    
    # Read markdown file
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        return 1
    
    # Extract headings for bookmark post-processing
    headings = extract_markdown_headings(markdown_content)

    # Convert markdown to HTML
    html_content = markdown_to_html(markdown_content, font_url, font_family)
    
    # Save temporary HTML file
    temp_html = input_path.parent / f"{input_path.stem}_temp.html"
    try:
        with open(temp_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
    except Exception as e:
        print(f"Error writing temporary HTML file: {e}", file=sys.stderr)
        return 1
    
    print(f"Temporary HTML: {temp_html}")
    
    # Try to convert using playwright
    try:
        from playwright.sync_api import sync_playwright
        
        print("Rendering PDF with Playwright...")
        
        with sync_playwright() as p:
            # Launch browser in headless mode to avoid display issues
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Load the HTML file
            page.goto(f'file://{temp_html}')
            
            # Wait for MathJax to finish rendering
            print("Waiting for MathJax to render...")
            page.wait_for_function(
                "window.MathJax && window.MathJax.typesetPromise",
                timeout=5000
            )
            page.evaluate("window.MathJax.typesetPromise()")
            page.wait_for_timeout(2000)  # Extra wait for rendering
            
            # Generate PDF
            pdf_options = {
                'path': str(output_path),
                'format': 'Letter',
                'margin': {
                    'top': '0.75in',
                    'right': '0.75in',
                    'bottom': '0.75in',
                    'left': '0.75in'
                },
                'print_background': True
            }
            
            # Add tagged and outline options when supported.
            # - tagged=True improves accessibility/link preservation
            # - outline=True embeds the document outline/bookmarks so
            #   PDF viewers can show jumpable section markers for headings.
            try:
                page.pdf(**pdf_options, tagged=True, outline=True)
            except TypeError:
                # Fall back progressively for older Playwright versions.
                try:
                    page.pdf(**pdf_options, tagged=True)
                except TypeError:
                    page.pdf(**pdf_options)
            
            browser.close()
        
        print(f"✓ PDF created successfully: {output_path}")

        bookmarks_added, bookmark_message = add_pdf_bookmarks(output_path, headings)
        if bookmarks_added:
            print(f"✓ {bookmark_message}")
        else:
            print(f"Note: {bookmark_message}")
        
        # Open the PDF automatically if requested
        if auto_open:
            print("Opening PDF...")
            open_file(str(output_path))
        
    except ImportError:
        print("\nError: playwright is not installed.", file=sys.stderr)
        print("Please install it with:", file=sys.stderr)
        print("  pip install playwright", file=sys.stderr)
        print("  playwright install chromium", file=sys.stderr)
        print(f"\nAlternatively, open this HTML file in a browser and print to PDF:", file=sys.stderr)
        print(f"  {temp_html}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error generating PDF: {e}", file=sys.stderr)
        print(f"\nYou can still open the HTML file in a browser and print to PDF:", file=sys.stderr)
        print(f"  {temp_html}", file=sys.stderr)
        return 1
    
    # Clean up temporary HTML file
    try:
        temp_html.unlink()
        print("Cleaned up temporary files.")
    except:
        pass
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Convert markdown files with LaTeX math to PDF',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s study_guide.md
  %(prog)s study_guide.md my_output.pdf
  %(prog)s study_guide.md output.pdf "https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600;700&display=swap"
  %(prog)s study_guide.md --no-open

If output file exists, you'll be prompted to overwrite or create a numbered copy like (1), (2), etc.
        """
    )
    
    parser.add_argument('input', help='Input markdown file')
    parser.add_argument('output', nargs='?', default=None, help='Output PDF file (optional, defaults to input name with .pdf)')
    parser.add_argument('font', nargs='?', default=None, help='Google Fonts CSS URL (optional, defaults to Nunito Sans)')
    parser.add_argument('--no-open', action='store_true', help='Do not automatically open the PDF after creation')
    
    if len(sys.argv) == 1:
        print("Usage: python md_to_pdf.py input.md [output.pdf] [font_url] [--no-open]")
        return 0

    args = parser.parse_args()
    
    return convert_to_pdf(args.input, args.output, args.font, auto_open=not args.no_open)


if __name__ == '__main__':
    sys.exit(main())