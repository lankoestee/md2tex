import re

def convert_references(file_path):
    """
    Convert all [@xxx] references in a Markdown file to [n] format with consistent numbering.

    :param file_path: Path to the Markdown file to process.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Find all unique [@xxx] patterns
    pattern = r'\[@(\w+)\]'
    matches = re.findall(pattern, content)

    # Assign unique numbers to each reference
    reference_map = {ref: str(i + 1) for i, ref in enumerate(dict.fromkeys(matches))}

    # Replace [@xxx] with [n]
    def replace_reference(match):
        return f"[{reference_map[match.group(1)]}]"

    updated_content = re.sub(pattern, replace_reference, content)

    # Write the updated content back to the file
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(updated_content)

    print("References converted successfully!")

# Example usage
# Replace 'your_markdown_file.md' with the path to your file
convert_references('开题报告.md')
