"""Unit tests for the PDF generation service."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from models.purchase_order import PurchaseOrder
from models.supplier import Supplier
from services.pdf_generator import POPDFGenerator, PDFGenerationError, pen_line_totals


def test_pen_line_totals() -> None:
    sub, igv, tot = pen_line_totals(
        [{"product_name": "X", "quantity": 10, "unit_price": 100.0}]
    )
    assert sub == Decimal("1000.00")
    assert igv == Decimal("180.00")
    assert tot == Decimal("1180.00")


@pytest.fixture
def pdf_generator() -> POPDFGenerator:
    return POPDFGenerator()


@pytest.fixture
def sample_purchase_order() -> Mock:
    po = Mock(spec=PurchaseOrder)
    po.request_id = "REQ-2026-001"
    po.id = 1
    po.created_at = datetime.now()
    po.supplier_id = 1
    return po


@pytest.fixture
def sample_supplier() -> Mock:
    supplier = Mock(spec=Supplier)
    supplier.id = 1
    supplier.company_name = "TechSupplier SAC"
    supplier.ruc = "20123456789"
    supplier.email = "ventas@techsupplier.com.pe"
    return supplier


@pytest.fixture
def sample_items() -> list[dict]:
    return [
        {
            "product_name": "Laptop Dell Inspiron",
            "quantity": 10,
            "unit_price": 300.00,
        }
    ]


def test_pdf_generator_initialization(pdf_generator: POPDFGenerator) -> None:
    assert pdf_generator is not None
    assert hasattr(pdf_generator, "output_dir")
    assert hasattr(pdf_generator, "font_config")


def test_generate_purchase_order_pdf_success(
    pdf_generator: POPDFGenerator,
    sample_purchase_order: Mock,
    sample_supplier: Mock,
    sample_items: list[dict],
) -> None:
    with (
        patch("pathlib.Path.mkdir"),
        patch("services.pdf_generator.HTML") as mock_html,
    ):
        mock_html_instance = Mock()
        mock_html.return_value = mock_html_instance
        mock_html_instance.write_pdf = Mock()

        result = pdf_generator.generate_purchase_order_pdf(
            sample_purchase_order,
            sample_supplier,
            sample_items,
        )

        assert isinstance(result, str)
        assert result.startswith("generated_pos/")
        assert result.endswith(".pdf")
        assert "REQ-2026-001" in result
        mock_html_instance.write_pdf.assert_called_once()


def test_generate_purchase_order_pdf_failure(
    pdf_generator: POPDFGenerator,
    sample_purchase_order: Mock,
    sample_supplier: Mock,
    sample_items: list[dict],
) -> None:
    with patch("pathlib.Path.mkdir"), patch("services.pdf_generator.HTML") as mock_html:
        mock_html_instance = Mock()
        mock_html.return_value = mock_html_instance
        mock_html_instance.write_pdf.side_effect = OSError("WeasyPrint error")

        with pytest.raises(PDFGenerationError):
            pdf_generator.generate_purchase_order_pdf(
                sample_purchase_order,
                sample_supplier,
                sample_items,
            )


def test_generate_po_html(
    pdf_generator: POPDFGenerator,
    sample_purchase_order: Mock,
    sample_supplier: Mock,
    sample_items: list[dict],
) -> None:
    sample_purchase_order.payload = None
    html_content = pdf_generator._generate_po_html(
        sample_purchase_order,
        sample_supplier,
        sample_items,
    )

    assert "<!DOCTYPE html>" in html_content
    assert "Purchase Order" in html_content
    assert sample_purchase_order.request_id in html_content
    assert sample_supplier.company_name in html_content
    assert sample_supplier.ruc in html_content
    assert "Laptop Dell Inspiron" in html_content
    assert "10" in html_content
    assert "300.00" in html_content
    assert "PEN" in html_content
    assert "IGV" in html_content
    assert "TOTAL" in html_content
    assert "Anexo: precios consultados" not in html_content


def test_generate_po_html_includes_market_appendix(
    pdf_generator: POPDFGenerator,
    sample_purchase_order: Mock,
    sample_supplier: Mock,
    sample_items: list[dict],
) -> None:
    sample_purchase_order.payload = {
        "external_market_snapshot": [
            {
                "source_id": 1,
                "source_name": "ScraperAPI (MercadoLibre PE)",
                "adapter_key": "scraperapi",
                "query": "Laptop Dell",
                "product_name": "Laptop Dell Inspiron 15",
                "unit_price": "2599.00",
                "currency": "PEN",
                "url": "https://articulo.mercadolibre.com.pe/MPE-9999",
                "lead_time_days": 5,
            },
            {
                "source_id": 2,
                "source_name": "ScraperAPI (Amazon US)",
                "adapter_key": "scraperapi",
                "query": "Laptop Dell",
                "product_name": "Dell Inspiron 15 3000",
                "unit_price": "549.99",
                "currency": "USD",
                "url": "https://www.amazon.com/dp/B0EXAMPLE",
                "lead_time_days": 12,
            },
        ]
    }

    html_content = pdf_generator._generate_po_html(
        sample_purchase_order,
        sample_supplier,
        sample_items,
    )

    assert "Anexo: precios consultados en marketplaces" in html_content
    assert "[scraperapi] ScraperAPI (MercadoLibre PE)" in html_content
    assert "[scraperapi] ScraperAPI (Amazon US)" in html_content
    assert "2599.00 PEN" in html_content
    assert "549.99 USD" in html_content
    assert "https://www.amazon.com/dp/B0EXAMPLE" in html_content


def test_cleanup_old_pdfs(pdf_generator: POPDFGenerator) -> None:
    mock_file = Mock()
    mock_file.stat.return_value.st_mtime = 1_000_000
    mock_file.unlink = Mock()

    with patch("pathlib.Path.glob", return_value=[mock_file]), patch(
        "services.pdf_generator.datetime"
    ) as mock_dt:
        mock_now = Mock()
        mock_now.timestamp.return_value = 2_000_000_000
        mock_dt.now.return_value = mock_now

        result = pdf_generator.cleanup_old_pdfs(days_to_keep=30)

        mock_file.unlink.assert_called_once()
        assert result == 1
