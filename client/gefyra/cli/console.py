from datetime import datetime

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.shortcuts.progress_bar import formatters
from prompt_toolkit.styles import Style

styles = Style.from_dict({"error": "#FF1820", "success": "#31F565", "bold": "bold"})

create_pbar = Style.from_dict(
    {
        "percentage": "bg:#ffff00 #000000",
        "current": "#448844",
        "bar": "",
    }
)

cluster_create_formatters = [
    formatters.Text("[", style="class:percentage"),
    formatters.Percentage(),
    formatters.Text("]", style="class:percentage"),
    formatters.Text(" "),
    formatters.Bar(sym_a="=", sym_b=">", sym_c="."),
    formatters.Text("  "),
]


def last_event_by_timestamp_toolbar(
    events: dict[datetime, dict[str, str]]
) -> FormattedText:
    events = list(events.items())
    if len(events) == 0:
        return FormattedText([("class:info", "Waiting for events...")])
    else:
        timestamp, curr_event = events[-1]
        reason = curr_event["reason"]
        message = curr_event["message"]
        return FormattedText(
            [
                (
                    f"class:{'error' if reason == 'Error' else 'info'}",
                    f"{reason}: {message}",
                )
            ]
        )


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
