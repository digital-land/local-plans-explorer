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
