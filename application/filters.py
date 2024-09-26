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
    if status == Status.FOR_PUBLICATION:
        return "yellow"
    if status == Status.PUBLISHED:
        return "green"
    if status == Status.NOT_FOR_PUBLICATION:
        return "red"
