import sys
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style
from prompt_toolkit.output.win32 import NoConsoleScreenBufferError

styles = Style.from_dict({"error": "#FF1820", "success": "#31F565", "bold": "bold"})


def print_text(formatted_text: FormattedText, text: str):
    if sys.platform == "win32":
        try:
            print_formatted_text(formatted_text, styles)
        except NoConsoleScreenBufferError:
            print(text)
    else:
        print_formatted_text(formatted_text, styles)


def heading(text: str):
    print_text(FormattedText([("class:bold", f"{text}")]), text)


def error(text: str):
    print_text(FormattedText([("class:error", f"Error: {text}")]), text)


def info(text: str):
    print_text(FormattedText([("class:info", f"{text}")]), text)


def success(text: str):
    print_text(FormattedText([("class:success", f"{text}")]), text)
