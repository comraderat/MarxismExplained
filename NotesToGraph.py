
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from os.path import relpath
import re
import yaml


@dataclass
class Note:
    path: Path
    title: str
    content: str
    parent_name: Optional[str] = None
    child_names: list[str] = field(default_factory=list)

    parent: Optional["Note"] = None
    children: list["Note"] = field(default_factory=list)

    metadata: dict = field(default_factory=dict)


    def unlinked_clone(self) -> "Note":
        """Return a clone of the note without parent/child references."""
        return Note(
            path=self.path,
            title=self.title,
            content=self.content,
            parent_name=self.parent_name,
            child_names=self.child_names.copy(),
        )


def extract_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from a Markdown file."""
    match = re.match(
        r"^---\s*\n(.*?)\n---\s*(?:\n|$)",
        content,
        re.DOTALL
    )

    if not match:
        return {}

    return yaml.safe_load(match.group(1)) or {}


def extract_links(value) -> list[str]:
    """Extract note names from Obsidian-style wikilinks."""
    if not value:
        return []


    if isinstance(value, list):
        value = [extract_links(item) for item in value]
    
    if isinstance(value, str):
        value = [value]

    return [
        link.group(1).strip()
        for item in value
        if (link := re.fullmatch(r"\[\[(.*?)\]\]", str(item).strip()))
    ]


def parse_note(path: Path) -> Note:
    """Parse a Markdown file into a Note object."""
    content = path.read_text(encoding="utf-8")

    frontmatter = extract_frontmatter(content)

    return Note(
        path=path,
        title=path.stem,
        content=content,
        parent_name=(
            extract_links(frontmatter.get("parent")) or [None]
        )[0],
        child_names=extract_links(frontmatter.get("children")),
    )


def build_tree(notes: list[Note]) -> list[Note]:
    """Resolve parent/child references and return root notes."""
    # Index notes by filename and title.
    index = {}

    for note in notes:
        index[note.path.stem] = note
        index[note.title] = note

    # Resolve relationships.
    for note in notes:
        if note.parent_name:
            parent = index.get(note.parent_name)

            if parent:
                note.parent = parent

        for child_name in note.child_names:
            child = index.get(child_name)

            if child:
                child.parent = note

    # Build children lists from parent references.
    for note in notes:
        if note.parent and note not in note.parent.children:
            note.parent.children.append(note)

    # Return notes without parents.
    return [note for note in notes if note.parent is None]


def print_tree(notes: list[Note], indent: int = 0):
    """Print the resulting hierarchy."""
    for note in notes:
        print("  " * indent + f"- {note.title} ({note.path})")
        print_tree(note.children, indent + 1)


def load_notes(directory: str) -> list[Note]:
    """Load all Markdown files recursively."""
    root = Path(directory).expanduser()

    # Resolve relative paths from the current directory first, then from this
    # script's directory so launching the script elsewhere still works.
    if not root.is_absolute() and not root.exists():
        root = Path(__file__).resolve().parent / root

    if not root.is_dir():
        raise FileNotFoundError(f"Notes directory not found: {root.resolve()}")

    paths = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() == ".md"
    )
    if not paths:
        raise FileNotFoundError(f"No Markdown files found in: {root.resolve()}")

    return [parse_note(path) for path in paths]


# Cloning

def get_children_clone(note: Note, depth: int) -> list[Note]:
    """Get children of a note up to a certain depth."""
    if depth <= 0:
        return []

    children = []
    for child in note.children:
        children.append(child.unlinked_clone())
        children.extend(get_children_clone(child, depth - 1))

    return children

def get_self_and_siblings_clone(note: Note, sibling_child_depth: int) -> list[Note]:
    """Get the note itself and its siblings and their children up to a certain depth."""
    if not note.parent:
        return [note.unlinked_clone()]
    
    siblings = []
    for sibling in note.parent.children:
        if sibling is not note:
            siblings.append(sibling.unlinked_clone())
            siblings.extend(get_children_clone(sibling, sibling_child_depth))

    return [note.unlinked_clone()] + siblings

def get_parents(note: Note, depth: int) -> list[Note]:
    """Get parents of a note up to a certain depth."""
    if depth <= 0 or not note.parent:
        return []

    parents = [note.parent.unlinked_clone()]
    parents.extend(get_parents(note.parent, depth - 1))

    return parents

def get_pruned_tree(start: Note) -> list[Note]:
    """Get a pruned tree of notes starting from a given note."""
    children = get_children_clone(start, 2)
    siblings = get_self_and_siblings_clone(start, 0)
    parents = get_parents(start, 2)
    total = children + siblings + parents

    unique = []
    titles = set()
    for note in total:
        if note.title not in titles:
            titles.add(note.title)
            unique.append(note)

    return build_tree(unique)  # Rebuild the tree structure for the pruned notes

def get_all_nodes(node: Note) -> list[Note]:
    items = [node]
    for child in node.children:
        items.extend(get_all_nodes(child))
    return items

def build_mermaid_code(root: Note, origin: Note):
    """Build a nested unordered list from the note tree."""
    text = ""
    nodes = get_all_nodes(root)
    count = 1
    link_node_letters = []
    
    for node in nodes:
        node.metadata["letter"] = "L" + str(count)
        count += 1
        if origin.path is not node.path:
            text += node.metadata["letter"] + f"[{node.title}]\n"
            link_node_letters.append(node.metadata["letter"])
        else:
            text += node.metadata["letter"] + f"[{node.title}]\n"


    for node in nodes:
        for child in node.children:
            text += node.metadata["letter"] + " --> " + child.metadata["letter"] + "\n"

    text += f"class {','.join(link_node_letters)} internal-link; "
    return text


def build_navigation_list(root: Note, origin: Note) -> str:
    text = ""
    text += "<li>\n"
    if root.path is not origin.path:
        text += f"<a href='{relpath(root.path, origin.path.parent).replace("\\", "/")}'>{root.title}</a>\n"
    else:
        text += f"{root.title}\n"
    for child in root.children:
        text += "<ul>\n"
        text += build_navigation_list(child, origin)
        text += "</ul>\n"
    text += "</li>\n"
    return text


def replace_graphs(note: Note):
    pruned_tree = get_pruned_tree(note)
    new_content = ""
    new_content += "<!-- id: generated mindmap -->\n```mermaid\ngraph TD\n"
    new_content += build_mermaid_code(pruned_tree[0], note)
    new_content += "\n```\n"

#     new_content += f"""
# Navigatie:
# <details>
# <ul>
# {build_navigation_list(pruned_tree[0], note)}
# </ul>
# </details>
# """

    new_content += "<!-- end: generated mindmap -->\n"

    

    note.content = re.sub(
        r"<!-- id: generated mindmap -->.*?<!-- end: generated mindmap -->",
        lambda _: new_content,
        note.content,
        flags=re.DOTALL,
    )

    #write the updated content back to the file
    note.path.write_text(note.content, encoding="utf-8")

if __name__ == "__main__":
    notes = load_notes("./docs")
    build_tree(notes)
    # print_tree(roots)
    for note in notes:
        replace_graphs(note)
