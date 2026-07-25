"""Iterate DOCX paragraphs and tables in their original XML order."""

from collections.abc import Iterator
from typing import Any, Literal

from docx.document import Document as DocumentObject
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

DOCXElementKind = Literal["paragraph", "table"]


def iter_docx_elements(parent: Any) -> Iterator[tuple[DOCXElementKind, Any]]:
    """Yield paragraph/table wrappers in package source order."""
    if isinstance(parent, DocumentObject):
        parent_element = parent.element.body
    else:
        parent_element = parent._element

    for child in parent_element.iterchildren():
        if isinstance(child, CT_P):
            yield "paragraph", Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield "table", Table(child, parent)
