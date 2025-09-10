"""Utility functions for parsing and formatting subtitle files."""

from typing import List, Dict, Any

def parse_srt_blocks(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse SRT file content into structured blocks."""
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.isdigit():
            index = line
            i += 1
            if i < len(lines) and '-->' in lines[i]:
                timestamp = lines[i].strip()
                i += 1
                text_lines = []
                while i < len(lines) and lines[i].strip() != '':
                    text_lines.append(lines[i].strip())
                    i += 1
                
                blocks.append({
                    'type': 'subtitle',
                    'index': index,
                    'timestamp': timestamp,
                    'content': '\n'.join(text_lines)
                })
            else: # It's just a number in the text
                blocks.append({'type': 'other', 'content': line})
        elif line:
            blocks.append({'type': 'other', 'content': line})
        
        i += 1 # Move to the next line

    return blocks

def format_srt_blocks(blocks: List[Dict[str, Any]]) -> str:
    """Format structured blocks back into SRT file content."""
    output_lines = []
    for block in blocks:
        if block['type'] == 'subtitle':
            output_lines.append(block['index'])
            output_lines.append(block['timestamp'])
            output_lines.append(block['content'])
            output_lines.append('')  # Separator
        else:
            output_lines.append(block['content'])
    
    return '\n'.join(output_lines)
