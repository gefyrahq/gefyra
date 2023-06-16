from datetime import datetime

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.shortcuts.progress_bar import formatters
from prompt_toolkit.styles import Style

styles = Style.from_dict({"error": "#FF1820", "success": "#31F565", "bold": "bold"})


def heading(text: str):
    print_formatted_text(FormattedText([("class:bold", f"{text}")]), style=styles)


def error(text: str):
    print_formatted_text(
        FormattedText([("class:error", f"Error: {text}")]), style=styles
    )


def info(text: str):
    print_formatted_text(FormattedText([("class:info", f"{text}")]), style=styles)


def success(text: str):
    print_formatted_text(FormattedText([("class:success", f"{text}")]), style=styles)
