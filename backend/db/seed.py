from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from models.product import Product
from models.supplier import Supplier


def _seed_rows() -> list[tuple[Supplier, list[Product]]]:
    rows: list[tuple[Supplier, list[Product]]] = [
        (
            Supplier(
                company_name="Distribuidora Andina SAC",
                ruc="20123456781",
                email="ventas@andina-dist.pe",
                phone="+51 1 234 5678",
                address="Av. Javier Prado Este 4200, Lima",
                rating=Decimal("8.40"),
            ),
            [
                Product(
                    name="Laptop empresarial 14\"",
                    description="Core i5, 16GB RAM, SSD 512GB",
                    sku="AND-LAP-14-01",
                    unit_price=Decimal("2850.00"),
                    lead_time_days=2,
                    available_stock=40,
                    minimum_order_quantity=1,
                ),
                Product(
                    name="Monitor LED 24\"",
                    description="Full HD, panel IPS",
                    sku="AND-MON-24-01",
                    unit_price=Decimal("620.00"),
                    lead_time_days=1,
                    available_stock=120,
                    minimum_order_quantity=2,
                ),
            ],
        ),
        (
            Supplier(
                company_name="Suministros del Norte EIRL",
                ruc="20567890123",
                email="compras@suministrosnorte.pe",
                phone="+51 44 712 334",
                address="Jr. Independencia 118, Trujillo",
                rating=Decimal("7.10"),
            ),
            [
                Product(
                    name="Escritorio melamina 1.40m",
                    description="Con cajonera lateral",
                    sku="SN-ESC-140-01",
                    unit_price=Decimal("890.00"),
                    lead_time_days=5,
                    available_stock=25,
                    minimum_order_quantity=1,
                ),
                Product(
                    name="Silla ergonómica mesh",
                    description="Reposabrazos ajustables",
                    sku="SN-SIL-MESH-01",
                    unit_price=Decimal("1150.00"),
                    lead_time_days=3,
                    available_stock=60,
                    minimum_order_quantity=1,
                ),
                Product(
                    name="Archivador metálico 4 gavetas",
                    description="Cerradura central",
                    sku="SN-ARC-4G-01",
                    unit_price=Decimal("1320.00"),
                    lead_time_days=4,
                    available_stock=15,
                    minimum_order_quantity=1,
                ),
            ],
        ),
        (
            Supplier(
                company_name="TechMype Perú SAC",
                ruc="20678901234",
                email="pedidos@techmype.pe",
                phone="+51 1 987 2211",
                address="Calle Las Orquídeas 210, Surco",
                rating=Decimal("9.05"),
            ),
            [
                Product(
                    name="Laptop empresarial 14\"",
                    description="Ryzen 7, 16GB RAM, SSD 1TB",
                    sku="TM-LAP-14-R7",
                    unit_price=Decimal("2999.00"),
                    lead_time_days=1,
                    available_stock=22,
                    minimum_order_quantity=1,
                ),
                Product(
                    name="Dock USB-C universal",
                    description="2 HDMI, RJ45, 100W PD",
                    sku="TM-DOCK-U01",
                    unit_price=Decimal("540.00"),
                    lead_time_days=1,
                    available_stock=200,
                    minimum_order_quantity=1,
                ),
            ],
        ),
        (
            Supplier(
                company_name="Papelería Central MYPE",
                ruc="20134567890",
                email="central@papeleriacentral.pe",
                phone="+51 1 333 9090",
                address="Av. Tacna 780, Cercado de Lima",
                rating=Decimal("6.80"),
            ),
            [
                Product(
                    name="Resma papel bond A4",
                    description="75g, 500 hojas",
                    sku="PC-PAP-A4-75",
                    unit_price=Decimal("24.90"),
                    lead_time_days=0,
                    available_stock=800,
                    minimum_order_quantity=10,
                ),
                Product(
                    name="Marcador permanente caja x12",
                    description="Punta fina negro",
                    sku="PC-MAR-12-BK",
                    unit_price=Decimal("36.50"),
                    lead_time_days=1,
                    available_stock=300,
                    minimum_order_quantity=5,
                ),
            ],
        ),
        (
            Supplier(
                company_name="Equipos Industriales Sur SAC",
                ruc="20456789012",
                email="ventas@eisur.pe",
                phone="+51 54 221 900",
                address="Panamericana Sur Km 12, Arequipa",
                rating=Decimal("7.65"),
            ),
            [
                Product(
                    name="Casco seguridad industrial",
                    description="Clase E, barbuquejo",
                    sku="EI-CAS-E01",
                    unit_price=Decimal("58.00"),
                    lead_time_days=2,
                    available_stock=500,
                    minimum_order_quantity=20,
                ),
                Product(
                    name="Guantes nitrilo caja x100",
                    description="Talla M",
                    sku="EI-GUA-NIT-M",
                    unit_price=Decimal("72.00"),
                    lead_time_days=2,
                    available_stock=150,
                    minimum_order_quantity=5,
                ),
                Product(
                    name="Botín dieléctrico",
                    description="Puntera composite",
                    sku="EI-BOT-DIEL-01",
                    unit_price=Decimal("189.00"),
                    lead_time_days=6,
                    available_stock=80,
                    minimum_order_quantity=1,
                ),
            ],
        ),
        (
            Supplier(
                company_name="Logística Rápida 24",
                ruc="20987654321",
                email="ops@logistica24.pe",
                phone="+51 1 555 1200",
                address="Av. Argentina 4793, Callao",
                rating=Decimal("8.90"),
            ),
            [
                Product(
                    name="Cinta embalaje transparente pack x6",
                    description="48mm x 100m",
                    sku="L24-EMB-T6",
                    unit_price=Decimal("42.00"),
                    lead_time_days=1,
                    available_stock=600,
                    minimum_order_quantity=5,
                ),
                Product(
                    name="Caja cartón triple onda",
                    description="60x40x40 cm",
                    sku="L24-CAJ-604040",
                    unit_price=Decimal("18.50"),
                    lead_time_days=1,
                    available_stock=2000,
                    minimum_order_quantity=50,
                ),
            ],
        ),
        (
            Supplier(
                company_name="Herramientas Pro Lima",
                ruc="20345678901",
                email="ventas@herramientaspro.pe",
                phone="+51 1 678 4321",
                address="Av. Colonial 2401, Los Olivos",
                rating=Decimal("7.95"),
            ),
            [
                Product(
                    name="Taladro percutor 18V kit",
                    description="2 baterías, maletín",
                    sku="HP-TAL-18V-K",
                    unit_price=Decimal("890.00"),
                    lead_time_days=2,
                    available_stock=35,
                    minimum_order_quantity=1,
                ),
                Product(
                    name="Juego llaves combinadas 12 pcs",
                    description="Cromo vanadio",
                    sku="HP-LLV-COM-12",
                    unit_price=Decimal("210.00"),
                    lead_time_days=3,
                    available_stock=70,
                    minimum_order_quantity=1,
                ),
            ],
        ),
        (
            Supplier(
                company_name="Alimentos Mayorista del Centro",
                ruc="20765432109",
                email="b2b@amcentro.pe",
                phone="+51 1 402 7788",
                address="Mercado Mayorista Santa Anita, Módulo 12",
                rating=Decimal("6.50"),
            ),
            [
                Product(
                    name="Aceite vegetal bidón 5L",
                    description="Alto oleico",
                    sku="AM-ACE-5L-01",
                    unit_price=Decimal("48.90"),
                    lead_time_days=1,
                    available_stock=400,
                    minimum_order_quantity=10,
                ),
                Product(
                    name="Azúcar rubia saco 50kg",
                    description="Grado A",
                    sku="AM-AZU-50KG",
                    unit_price=Decimal("198.00"),
                    lead_time_days=2,
                    available_stock=120,
                    minimum_order_quantity=2,
                ),
            ],
        ),
        (
            Supplier(
                company_name="Servicios Integrales Costa",
                ruc="20890123456",
                email="contacto@sintegrales.pe",
                phone="+51 1 222 8899",
                address="Malecón de la Reserva 1030, Miraflores",
                rating=Decimal("8.00"),
            ),
            [
                Product(
                    name="Servicio instalación UPS 3KVA",
                    description="Incluye puesta en marcha",
                    sku="SI-UPS-3K-INST",
                    unit_price=Decimal("450.00"),
                    lead_time_days=7,
                    available_stock=999,
                    minimum_order_quantity=1,
                ),
                Product(
                    name="Mantenimiento aire acondicionado split",
                    description="Hasta 18000 BTU",
                    sku="SI-MANT-AC-18K",
                    unit_price=Decimal("220.00"),
                    lead_time_days=4,
                    available_stock=999,
                    minimum_order_quantity=1,
                ),
            ],
        ),
        (
            Supplier(
                company_name="Importaciones Pacífico SAC",
                ruc="20156789012",
                email="import@pacifico-import.pe",
                phone="+51 1 711 3344",
                address="Av. El Derby 254, Santiago de Surco",
                rating=Decimal("7.25"),
            ),
            [
                Product(
                    name="Router WiFi 6 empresarial",
                    description="Dual WAN, 4 LAN",
                    sku="IP-RTR-W6-01",
                    unit_price=Decimal("1180.00"),
                    lead_time_days=10,
                    available_stock=45,
                    minimum_order_quantity=1,
                ),
                Product(
                    name="Switch administrable 24 puertos",
                    description="PoE+ 370W",
                    sku="IP-SW-24P-01",
                    unit_price=Decimal("2890.00"),
                    lead_time_days=10,
                    available_stock=18,
                    minimum_order_quantity=1,
                ),
                Product(
                    name="Cable UTP Cat6 bobina 305m",
                    description="Cobre sólido",
                    sku="IP-UTP6-305",
                    unit_price=Decimal("780.00"),
                    lead_time_days=8,
                    available_stock=30,
                    minimum_order_quantity=1,
                ),
            ],
        ),
    ]
    return rows


def seed() -> None:
    engine = create_engine(settings.sync_database_url, future=True)
    Session = sessionmaker(bind=engine, future=True)
    with Session.begin() as session:
        session.execute(
            text(
                "TRUNCATE procurement_logs, suppliers RESTART IDENTITY CASCADE"
            )
        )
        for supplier, products in _seed_rows():
            session.add(supplier)
            session.flush()
            for p in products:
                p.supplier_id = supplier.id
                session.add(p)


def main() -> None:
    seed()


if __name__ == "__main__":
    main()
