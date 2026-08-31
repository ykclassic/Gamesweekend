"""Compatibility shim for gspread 6.x's Worksheet.update argument order.

The application historically used the pre-6.x positional form:
    worksheet.update(range_name, values)

gspread 6.x expects:
    worksheet.update(values, range_name)

Keep the application behavior compatible while allowing the deployed
requirements to remain on the current gspread release.
"""

try:
    from gspread.worksheet import Worksheet

    _original_update = Worksheet.update

    def _update_compat(self, values, range_name=None, *args, **kwargs):
        if isinstance(values, str) and range_name is not None:
            if isinstance(range_name, (list, tuple)):
                values, range_name = range_name, values
            elif isinstance(range_name, str) and _looks_like_a1_range(values) and not _looks_like_a1_range(range_name):
                values, range_name = range_name, values
        return _original_update(self, values, range_name, *args, **kwargs)

    def _looks_like_a1_range(value):
        if not isinstance(value, str) or not value:
            return False
        # Covers the application's cells/ranges such as F1, A1:D1 and A:C.
        import re
        return bool(re.fullmatch(r"(?:[A-Za-z]{1,3}\d+(?::[A-Za-z]{1,3}\d+)?|[A-Za-z]{1,3}(?::[A-Za-z]{1,3})?)", value))

    Worksheet.update = _update_compat
except Exception:
    # Never prevent the application from starting if gspread changes its API.
    pass
