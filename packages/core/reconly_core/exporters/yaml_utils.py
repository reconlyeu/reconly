"""YAML utility functions for exporters."""


def yaml_escape(value: str) -> str:
    """Escape a string value for YAML frontmatter.

    Wraps in double quotes if the value contains special YAML characters
    like colons, which would otherwise break YAML parsing.
    """
    if not value:
        return '""'
    # Characters that require quoting in YAML
    special_chars = set(':{}[]&*#?|-><!%@\'"\\n')
    if any(c in special_chars for c in value):
        # Escape backslashes and double quotes, then wrap in quotes
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return value
