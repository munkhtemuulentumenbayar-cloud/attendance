"""
Хамааралгүй (zero-dependency) Excel .xlsx бичигч.
Зөвхөн stdlib ашиглана — openpyxl шаардлагагүй.
"""
from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

# ---------------------------------------------------------------- стилүүд
# 0 default | 1 title | 2 subtitle | 3 header | 4 text | 5 number(0.00)
# 6 red bold | 7 bold | 8 bold number
STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="164" formatCode="0.00"/></numFmts>
<fonts count="6">
<font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="16"/><color rgb="FF1F3864"/><name val="Calibri"/></font>
<font><i/><sz val="10"/><color rgb="FF555555"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><color rgb="FFC00000"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><color rgb="FF1F3864"/><name val="Calibri"/></font>
</fonts>
<fills count="4">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF2F5597"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFDDEBF7"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color rgb="FF9CB3D4"/></left><right style="thin"><color rgb="FF9CB3D4"/></right>
<top style="thin"><color rgb="FF9CB3D4"/></top><bottom style="thin"><color rgb="FF9CB3D4"/></bottom><diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="9">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="3" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
  <alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1">
  <alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1" applyAlignment="1">
  <alignment horizontal="right" vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1">
  <alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="5" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
  <alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="164" fontId="5" fillId="3" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
  <alignment horizontal="right" vertical="center"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
{sheet_overrides}
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def col_letter(idx: int) -> str:
    s = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def _cell_xml(ref: str, value, style: int) -> str:
    if value is None or value == "":
        return f'<c r="{ref}" s="{style}"/>'
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, (int, float)):
        return f'<c r="{ref}" s="{style}" t="n"><v>{value}</v></c>'
    return (f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">'
            f'{escape(str(value))}</t></is></c>')


def _sheet_xml(sheet: dict) -> str:
    rows = sheet.get("rows", [])
    cols = sheet.get("cols", [])
    width_xml = ""
    if cols:
        width_xml = "<cols>" + "".join(
            f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>'
            for i, w in enumerate(cols)) + "</cols>"
    row_parts = []
    for r_i, row in enumerate(rows, start=1):
        cells = "".join(
            _cell_xml(f"{col_letter(c_i)}{r_i}", val, style)
            for c_i, (val, style) in enumerate(row) if val is not None)
        row_parts.append(f'<row r="{r_i}">{cells}</row>')
    freeze = sheet.get("freeze")
    pane = ""
    if freeze:
        # freeze: мөрүүдийн тоо (int) эсвэл "A4" хэлбэрийн нүд
        if isinstance(freeze, str):
            digits = "".join(ch for ch in freeze if ch.isdigit())
            freeze = int(digits) - 1 if digits else 0
        if freeze and int(freeze) > 0:
            freeze = int(freeze)
            pane = (f'<sheetViews><sheetView workbookViewId="0"><pane ySplit="{freeze}" '
                    f'topLeftCell="A{freeze+1}" activePane="bottomLeft" state="frozen"/>'
                    f'</sheetView></sheetViews>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'{pane}{width_xml}<sheetData>{"".join(row_parts)}</sheetData>'
            '<pageMargins left="0.4" right="0.4" top="0.5" bottom="0.5" header="0.3" footer="0.3"/>'
            '</sheetSettings></worksheet>').replace("</sheetSettings>", "")


def write_xlsx(sheets: list[dict]) -> bytes:
    """sheets: [{'name': str, 'cols': [widths], 'rows': [[(value, style), ...]], 'freeze': int}]"""
    buf = io.BytesIO()
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(len(sheets)))
    sheet_entries = "".join(
        f'<sheet name="{escape(s["name"][:31])}" sheetId="{i+1}" r:id="rId{i+1}"/>'
        for i, s in enumerate(sheets))
    wb_rels = "".join(
        f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        f'relationships/worksheet" Target="worksheets/sheet{i+1}.xml"/>'
        for i in range(len(sheets)))
    wb_rels += (f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/'
                f'officeDocument/2006/relationships/styles" Target="styles.xml"/>')

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES.format(sheet_overrides=overrides))
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   f'<sheets>{sheet_entries}</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'{wb_rels}</Relationships>')
        z.writestr("xl/styles.xml", STYLES_XML)
        for i, sheet in enumerate(sheets):
            z.writestr(f"xl/worksheets/sheet{i+1}.xml", _sheet_xml(sheet))
    return buf.getvalue()
