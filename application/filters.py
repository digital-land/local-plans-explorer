from datetime import datetime

from application.models import Status


def get_date_part(d_str, part):
    parts = d_str.split("-")
    if part == "YYYY":
        return parts[0]
    if part == "MM":
        return parts[1]
    return parts[2]


def get_status_colour(status: Status) -> str:
    if status == Status.FOR_REVIEW:
        return "light-blue"
    if status == Status.FOR_PLATFORM:
        return "yellow"
    if status == Status.EXPORTED:
        return "green"
    if status == Status.NOT_FOR_PLATFORM:
        return "red"


def timetable_status_colour(status: str) -> str:
    match status:
        case "completed":
            return "green"
        case "not started":
            return "grey"
        case "started":
            return "yellow"
        case _:
            return "grey"


def short_date_filter(date_str):
    if not date_str or date_str.strip() == "":
        return ""

    # Handle date ranges with "to"
    if " to " in date_str:
        start_date, end_date = date_str.split(" to ")
        return f"{short_date_filter(start_date)} to {short_date_filter(end_date)}"
    if "/" in date_str:
        parts = date_str.split("/")
        try:
            match len(parts):
                case 3:  # DD/MM/YYYY
                    date = datetime.strptime(date_str, "%d/%m/%Y")
                    return date.strftime("%-d{} %B %Y").format(
                        "st" if date.day == 1 else "th"
                    )
                case 2:  # MM/YYYY
                    date = datetime.strptime(date_str, "%m/%Y")
                    return date.strftime("%B %Y")
                case 1:  # YYYY
                    return parts[0]  # Just return the year
                case _:
                    return date_str
        except ValueError:
            return date_str
    else:
        parts = date_str.split("-")
        try:
            match len(parts):
                case 3:  # YYYY-MM-DD
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    return date.strftime("%-d{} %B %Y").format(
                        "st" if date.day == 1 else "th"
                    )
                case 2:  # YYYY-MM
                    date = datetime.strptime(date_str, "%Y-%m")
                    return date.strftime("%B %Y")
                case 1:  # YYYY
                    return parts[0]  # Just return the year
                case _:
                    return date_str
        except ValueError:
            return date_str
