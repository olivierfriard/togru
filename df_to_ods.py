from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

import pandas as pd
from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P


def dataframe_to_ods(
    df: pd.DataFrame,
    sheet_name: str = "Risultati",
    include_index: bool = False,
) -> BytesIO:
    """
    Converte un pandas DataFrame in un file ODS in memoria.

    Restituisce
    -----------
    BytesIO
        Buffer posizionato all'inizio, pronto per essere inviato come file.
    """

    output = BytesIO()

    doc = OpenDocumentSpreadsheet()
    table = Table(name=str(sheet_name))

    # Header
    header_row = TableRow()

    if include_index:
        index_name = df.index.name if df.index.name is not None else "index"
        header_row.addElement(_make_cell(index_name))

    for column in df.columns:
        header_row.addElement(_make_cell(str(column)))

    table.addElement(header_row)

    # Data
    for index_value, row_data in df.iterrows():
        row = TableRow()

        if include_index:
            row.addElement(_make_cell(_normalize_pandas_value(index_value)))

        for value in row_data:
            row.addElement(_make_cell(_normalize_pandas_value(value)))

        table.addElement(row)

    doc.spreadsheet.addElement(table)

    doc.write(output)
    output.seek(0)

    return output


def _normalize_pandas_value(value: Any) -> Any:
    """
    Converte valori pandas/numpy in valori Python gestibili da odfpy.
    """

    if value is pd.NA:
        return None

    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.to_pydatetime()

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def _make_cell(value: Any) -> TableCell:
    """
    Converte un valore Python in una cella ODS tipizzata correttamente.
    """

    cell = TableCell()

    if value is None:
        return cell

    if isinstance(value, bool):
        cell.setAttribute("valuetype", "boolean")
        cell.setAttribute("booleanvalue", str(value).lower())
        cell.addElement(P(text="TRUE" if value else "FALSE"))
        return cell

    if isinstance(value, int) and not isinstance(value, bool):
        cell.setAttribute("valuetype", "float")
        cell.setAttribute("value", str(value))
        cell.addElement(P(text=str(value)))
        return cell

    if isinstance(value, float):
        cell.setAttribute("valuetype", "float")
        cell.setAttribute("value", repr(value))
        cell.addElement(P(text=str(value)))
        return cell

    if isinstance(value, Decimal):
        cell.setAttribute("valuetype", "float")
        cell.setAttribute("value", str(value))
        cell.addElement(P(text=str(value)))
        return cell

    if isinstance(value, datetime):
        iso_value = value.isoformat()
        cell.setAttribute("valuetype", "date")
        cell.setAttribute("datevalue", iso_value)
        cell.addElement(P(text=value.strftime("%Y-%m-%d %H:%M:%S")))
        return cell

    if isinstance(value, date):
        iso_value = value.isoformat()
        cell.setAttribute("valuetype", "date")
        cell.setAttribute("datevalue", iso_value)
        cell.addElement(P(text=iso_value))
        return cell

    text = str(value)
    cell.setAttribute("valuetype", "string")
    cell.addElement(P(text=text))
    return cell
