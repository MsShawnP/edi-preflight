def format_edi_date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[4:6]}/{value[6:8]}/{value[0:4]}"
    return value


def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def format_quantity(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"
