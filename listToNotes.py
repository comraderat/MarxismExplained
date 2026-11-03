
#!/usr/bin/env python3

import re
import json
import argparse
from pathlib import Path


def clean_filename(name):
    """Convert note title into a safe filename."""
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    return name.strip().rstrip('.')


def parse_markdown_list(content):
    """Parse nested unordered Markdown lists."""
    items = []
    stack = []

    for line in content.splitlines():
        match = re.match(r'^(\s*)([-*+])(\s+)(.+?)\s*$', line)

        if not match:
            continue

        indent = len(match.group(3).expandtabs(4))
        title = clean_filename(match.group(4).strip())

        # Find the parent based on indentation
        while stack and stack[-1][0] >= indent:
            stack.pop()

        parent = stack[-1][1] if stack else None

        item = {
            "title": title,
            "parent": parent,
            "children": [],
            "folderpath": []
        }

        items.append(item)

        if parent is not None:
            parent["children"].append(item)

        stack.append((indent, item))

    return items

def count_children(item):
    """Count total number of children for the current item recursively."""
    count = len(item["children"])
    for child in item["children"]:
        count += count_children(child)
    return count

def add_folder(item, new_folder_name):
    """Add a folder to the current item and rename its children."""
    item["folderpath"].append(new_folder_name)
    for child in item["children"]:
        add_folder(child, new_folder_name)

def generate_notes(items, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    filenames = {}

    # Check for duplicate filenames
    for item in items:
        filename = clean_filename(item["title"])

        if filename in filenames:
            raise ValueError(
                f"Duplicate note filename: {filename}"
            )

        filenames[filename] = item["title"]

    for item in items:

        title = item["title"]
        filename = clean_filename(title)

        # Count total number of children for the current item recursively
        child_count = count_children(item)
        if child_count >= 3:
            #Create folder for the note if it has more than 4 children
            add_folder(item, filename)  # Add folder and rename children with folder name prefix

        #add all folder paths to the note's folderpath
        filepath = Path(output_dir, *item["folderpath"], f"{filename}.md")
        #Create parent directories if they don't exist
        filepath.parent.mkdir(parents=True, exist_ok=True)

        frontmatter = "---\n"

        if item["parent"]:
            parent = item["parent"]
            frontmatter += f'parent: "[[{parent["title"]}]]"\n'

        frontmatter += "children:\n"
        for child in item["children"]:
            frontmatter += f'  - "[[{child["title"]}]]"\n'

        frontmatter += "---\n"

        frontmatter += f"""<!-- id: generated mindmap -->\n```mindmap
# Placeholder Mindmap
## Child item
### Child of child item
```\n<!-- end: generated mindmap -->\n"""

        frontmatter += "# Summary\n\n\n"
        frontmatter += "# Video's\n\n\n"
        frontmatter += "# Lesson plans\n\n\n"

        filepath.write_text(
            frontmatter,
            encoding="utf-8"
        )

        print(f"Created: {filepath}")


def execute(inputfile, outputdir):
    content = Path(inputfile).read_text(encoding="utf-8")

    items = parse_markdown_list(content)

    generate_notes(items, Path(outputdir))

    print(f"\nGenerated {len(items)} notes.")

def main():
    parser = argparse.ArgumentParser(
        description="Convert nested Markdown lists into Obsidian notes."
    )

    parser.add_argument("input", help="Input Markdown file")
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory (default: output)"
    )

    args = parser.parse_args()

    execute(args.input, args.output)


if __name__ == "__main__":
    # main()
    execute("old list.md", "Marxisme")
