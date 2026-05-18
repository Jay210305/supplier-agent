"""
PDF generation service for Purchase Orders using WeasyPrint.
Generates professional PDF POs in Peruvian Soles (PEN) format.
"""
import html as html_lib
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

from config import settings
from models.purchase_order import PurchaseOrder
from services.marketplace_fulfillment import SupplierPDFView

logger = logging.getLogger(__name__)

PDF_CONFIG = {
    "page_size": "A4",
    "margin_top": "20mm",
    "margin_bottom": "20mm",
    "margin_left": "15mm",
    "margin_right": "15mm",
    "font_size": "10pt",
}


def pen_line_totals(items: list[dict[str, Any]]) -> tuple[Decimal, Decimal, Decimal]:
    """Subtotal (ex IGV), IGV 18%, grand total in PEN."""
    subtotal = Decimal("0")
    for item in items:
        quantity = Decimal(str(item.get("quantity", 0)))
        unit_price = Decimal(str(item.get("unit_price", 0)))
        subtotal += quantity * unit_price
    igv = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
    grand = (subtotal + igv).quantize(Decimal("0.01"))
    subtotal = subtotal.quantize(Decimal("0.01"))
    return subtotal, igv, grand


class PDFGenerationError(Exception):
    """Base exception for PDF generation errors."""
    pass


class POPDFGenerator:
    """Generates PDF Purchase Orders using WeasyPrint."""

    def __init__(self) -> None:
        self.output_dir = Path(settings.GENERATED_POS_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.font_config = FontConfiguration()

    def generate_purchase_order_pdf(
        self,
        purchase_order: PurchaseOrder,
        supplier: SupplierPDFView,
        items: list[dict[str, Any]],
    ) -> str:
        """
        Generate a PDF Purchase Order and save it to the output directory.
        
        Args:
            purchase_order: PurchaseOrder ORM instance
            supplier: Supplier ORM instance
            items: List of item dictionaries with product info, quantity, price
            
        Returns:
            Relative path to the generated PDF file (for storage in DB)
            
        Raises:
            PDFGenerationError: If PDF generation fails
        """
        try:
            # Generate HTML content for the PO
            html_content = self._generate_po_html(purchase_order, supplier, items)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rid = purchase_order.request_id or f"ID{purchase_order.id}"
            filename = f"PO_{rid}_{timestamp}.pdf"
            file_path = self.output_dir / filename
            
            # Generate PDF using WeasyPrint
            HTML(string=html_content, base_url='').write_pdf(
                target=str(file_path),
                font_config=self.font_config,
                presentational_hints=True
            )
            
            # Return relative path for database storage
            relative_path = f"generated_pos/{filename}"
            logger.info(f"Generated PO PDF: {relative_path}")
            
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate PO PDF: {str(e)}")
            raise PDFGenerationError(f"PDF generation failed: {str(e)}")
    
    def _generate_po_html(
        self,
        purchase_order: PurchaseOrder,
        supplier: SupplierPDFView,
        items: list[dict[str, Any]],
    ) -> str:
        """
        Generate HTML content for the Purchase Order.
        
        Args:
            purchase_order: PurchaseOrder ORM instance
            supplier: Supplier ORM instance
            items: List of item dictionaries
            
        Returns:
            Complete HTML string for the PO
        """
        subtotal, igv_amount, total_amount = pen_line_totals(items)

        # Format dates
        po_date = purchase_order.created_at.strftime("%d/%m/%Y") if purchase_order.created_at else ""
        po_ref = purchase_order.request_id or f"PO-{purchase_order.id}"

        payload = purchase_order.payload if isinstance(purchase_order.payload, dict) else {}
        snapshot = payload.get("external_market_snapshot") or []
        if not isinstance(snapshot, list):
            snapshot = []
        appendix_html = self._render_market_snapshot_appendix(snapshot)
        
        # Build HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Purchase Order {po_ref}</title>
            <style>
                @page {{
                    size: A4;
                    margin: {PDF_CONFIG['margin_top']} {PDF_CONFIG['margin_right']} 
                            {PDF_CONFIG['margin_bottom']} {PDF_CONFIG['margin_left']};
                }}
                body {{
                    font-family: 'Helvetica', 'Arial', sans-serif;
                    font-size: {PDF_CONFIG['font_size']};
                    line-height: 1.4;
                    color: #000;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    border-bottom: 2px solid #333;
                    padding-bottom: 10px;
                }}
                .company-info {{
                    font-size: 14pt;
                    font-weight: bold;
                    margin-bottom: 5px;
                }}
                .po-title {{
                    font-size: 18pt;
                    font-weight: bold;
                    color: #2c3e50;
                    margin: 20px 0;
                }}
                .info-section {{
                    margin-bottom: 20px;
                }}
                .info-row {{
                    display: flex;
                    margin-bottom: 5px;
                }}
                .info-label {{
                    font-weight: bold;
                    width: 120px;
                }}
                .info-value {{
                    flex: 1;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                    font-weight: bold;
                }}
                .totals {{
                    margin: 30px 0;
                    font-size: 12pt;
                }}
                .total-row {{
                    display: flex;
                    justify-content: flex-end;
                    margin-bottom: 10px;
                }}
                .total-label {{
                    font-weight: bold;
                    margin-right: 10px;
                    width: 150px;
                    text-align: right;
                }}
                .total-value {{
                    font-weight: bold;
                    text-align: right;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #ccc;
                    font-size: 9pt;
                    text-align: center;
                    color: #666;
                }}
                .note {{
                    font-style: italic;
                    color: #555;
                    margin-top: 10px;
                }}
                .appendix {{
                    margin-top: 40px;
                    padding-top: 15px;
                    border-top: 1px dashed #999;
                    page-break-inside: avoid;
                }}
                .appendix-title {{
                    font-size: 13pt;
                    font-weight: bold;
                    color: #2c3e50;
                    margin-bottom: 6px;
                }}
                .appendix-lead {{
                    font-size: 9pt;
                    color: #555;
                    margin-bottom: 12px;
                }}
                table.appendix-table {{
                    font-size: 9pt;
                    margin-top: 0;
                }}
                table.appendix-table th,
                table.appendix-table td {{
                    padding: 5px 6px;
                }}
                .appendix-source {{
                    font-weight: bold;
                    white-space: nowrap;
                }}
                .appendix-url {{
                    color: #1a5fb4;
                    word-break: break-all;
                    font-size: 8pt;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="company-info">Supplier Agent - Sistema de Abastecimiento Inteligente</div>
                <div>RUC: 20567890123 | Email: compras@mype.com.pe</div>
                <div>Av. Ejemplo 123, Lima, Perú</div>
            </div>
            
            <div class="po-title">ORDEN DE COMPRA</div>
            
            <div class="info-section">
                <div class="info-row">
                    <span class="info-label">Número de OC:</span>
                    <span class="info-value">{po_ref}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha:</span>
                    <span class="info-value">{po_date}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Proveedor:</span>
                    <span class="info-value">{supplier.company_name}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">RUC Proveedor:</span>
                    <span class="info-value">{supplier.ruc}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Contacto:</span>
                    <span class="info-value">{supplier.email or 'N/A'}</span>
                </div>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Descripción</th>
                        <th>Cantidad</th>
                        <th>Precio Unitario (PEN)</th>
                        <th>Subtotal (PEN)</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # Add items
        for idx, item in enumerate(items, 1):
            quantity = Decimal(str(item.get('quantity', 0)))
            unit_price = Decimal(str(item.get('unit_price', 0)))
            item_subtotal = quantity * unit_price
            line_ccy = html_lib.escape(str(item.get("currency") or purchase_order.currency or "PEN"))
            
            html += f"""
                    <tr>
                        <td>{idx}</td>
                        <td>{item.get('product_name', item.get('product', 'Producto'))}</td>
                        <td>{quantity}</td>
                        <td>{unit_price:.2f} {line_ccy}</td>
                        <td>{item_subtotal:.2f} {line_ccy}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
            
            <div class="totals">
                <div class="total-row">
                    <span class="total-label">Subtotal:</span>
                    <span class="total-value">""" + f"{subtotal:.2f}" + """ PEN</span>
                </div>
                <div class="total-row">
                    <span class="total-label">IGV (18%):</span>
                    <span class="total-value">""" + f"{igv_amount:.2f}" + """ PEN</span>
                </div>
                <div class="total-row">
                    <span class="total-label">TOTAL:</span>
                    <span class="total-value">""" + f"{total_amount:.2f}" + """ PEN</span>
                </div>
            </div>
            """ + appendix_html + """

            <div class="footer">
                <p>Esta orden de compra está sujeta a los términos y condiciones estándar de nuestra empresa.</p>
                <p>Por favor, confirme la recepción de esta orden dentro de 24 horas.</p>
                <div class="note">
                    Documento generado electrónicamente - Sistema de Abastecimiento Inteligente
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    def _render_market_snapshot_appendix(snapshot: list[dict[str, Any]]) -> str:
        """Render the marketplace price-check appendix (empty string when none)."""
        if not snapshot:
            return ""

        rows: list[str] = []
        for listing in snapshot:
            try:
                price = Decimal(str(listing.get("unit_price", 0)))
            except Exception:
                continue
            source_label = html_lib.escape(
                f"[{listing.get('adapter_key', '?')}] {listing.get('source_name', '?')}"
            )
            query = html_lib.escape(str(listing.get("query", "")))
            product = html_lib.escape(str(listing.get("product_name", ""))[:200])
            currency = html_lib.escape(str(listing.get("currency", "PEN")))
            lead = listing.get("lead_time_days")
            lead_cell = f"{int(lead)} d" if lead is not None else "-"
            url = listing.get("url")
            if url:
                safe_url = html_lib.escape(str(url), quote=True)
                display_url = html_lib.escape(str(url)[:80])
                url_cell = f'<a class="appendix-url" href="{safe_url}">{display_url}</a>'
            else:
                url_cell = "-"
            rows.append(
                f"""
                    <tr>
                        <td class="appendix-source">{source_label}</td>
                        <td>{query}</td>
                        <td>{product}</td>
                        <td>{price:.2f} {currency}</td>
                        <td>{lead_cell}</td>
                        <td>{url_cell}</td>
                    </tr>
                """
            )

        return (
            """
            <div class="appendix">
                <div class="appendix-title">Anexo: precios consultados en marketplaces</div>
                <div class="appendix-lead">
                    Resultados externos consultados por el agente al momento de generar esta orden.
                    Solo informativo; no sustituye la cotización del proveedor seleccionado.
                </div>
                <table class="appendix-table">
                    <thead>
                        <tr>
                            <th>Fuente</th>
                            <th>Consulta</th>
                            <th>Producto</th>
                            <th>Precio</th>
                            <th>Entrega</th>
                            <th>Enlace</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            + "".join(rows)
            + """
                    </tbody>
                </table>
            </div>
            """
        )

    def cleanup_old_pdfs(self, days_to_keep: int = 30) -> int:
        """
        Clean up old PDF files to save disk space.
        
        Args:
            days_to_keep: Number of days to keep PDFs (default 30)
            
        Returns:
            Number of files deleted
        """
        try:
            cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
            deleted_count = 0
            
            for file_path in self.output_dir.glob("PO_*.pdf"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old PDF: {file_path.name}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old PDF files")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old PDFs: {str(e)}")
            return 0