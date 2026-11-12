"""
Comando de administración para poblar datos simulados realistas del mercado de Armenia y Quindío:
1. 5 Personas Naturales registradas en la app (`ActorRole.REPORTER`) con IDs codificados no secuenciales y `last_login` activo.
2. Presentaciones derivadas (`ProductPresentation`) para los 38 productos del catálogo (2 a 3 presentaciones por producto con distintas marcas y gramajes/volúmenes para comparación normalizada M-01).
3. Reportes de precios (`PriceReport`) combinando:
   - Precios Oficiales de Comercio (`OFFICIAL_MERCHANT`) emitidos por los representantes verificados (`comercio_ara`, `comercio_d1`, `comercio_carulla`, `comercio_olimpica`, `comercio_dollarcity`, etc.).
   - Reportes Comunitarios (`COMMUNITY_OCCASIONAL` / `COMMUNITY_FREQUENT`) emitidos por las 5 personas naturales registradas en distintos supermercados y minimercados de Armenia.
   - Promociones destacadas (`is_promotional=True`) y algunos reportes atípicos (`LOW_CONFIDENCE` / `ANOMALOUS`) para el panel de Moderación.

Ejecución:
    python manage.py seed_simulated_market_data
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import ActorRole, UserProfile, VerificationStatus
from accounts.services import (
    generate_encoded_entity_id,
    resolve_verified_source_type_for_actor,
    update_actor_reputation_after_report,
)
from catalog.models import Establishment, Product, ProductPresentation
from pricing.models import PriceReport
from pricing.services import ReportPriceUseCase, invalidate_product_comparison_cache

User = get_user_model()

NATURAL_PERSONS = [
    {
        "username": "camila_gomez",
        "email": "camila.gomez@gmail.com",
        "first_name": "Camila",
        "last_name": "Gómez Restrepo",
    },
    {
        "username": "andres_ospina",
        "email": "andres.ospina@outlook.com",
        "first_name": "Andrés Felipe",
        "last_name": "Ospina Cardona",
    },
    {
        "username": "valentina_rios",
        "email": "valentina.rios@gmail.com",
        "first_name": "Valentina",
        "last_name": "Ríos Londoño",
    },
    {
        "username": "santiago_cardona",
        "email": "santiago.cardona@yahoo.com",
        "first_name": "Santiago",
        "last_name": "Cardona Giraldo",
    },
    {
        "username": "laura_quintero",
        "email": "laura.quintero@gmail.com",
        "first_name": "Laura Sofía",
        "last_name": "Quintero Salazar",
    },
]

# Definición de presentaciones derivadas por nombre de producto molde (con precio base estimado en COP)
# Formato de cada tupla: (brand, presentation_name, quantity, unit, ean_suffix, base_price_cop)
PRODUCT_PRESENTATIONS_CATALOG: dict[str, list[tuple[str, str, str, str, str, int]]] = {
    "Tomate Chonto": [
        ("Cosecha Quindío", "Libra (500 g)", "500.000", "g", "0401", 2100),
        ("Cosecha Quindío", "Kilo Familiar (1 kg)", "1.000", "kg", "0402", 3900),
        ("Campo Noble", "Bandeja Seleccionada 750 g", "750.000", "g", "0403", 3400),
    ],
    "Cebolla Larga / Junca": [
        ("Cosecha Quindío", "Atado Libra (500 g)", "500.000", "g", "0501", 1900),
        ("Cosecha Quindío", "Atado Grande (1 kg)", "1.000", "kg", "0502", 3500),
    ],
    "Cebolla Cabezona": [
        ("Cosecha Quindío", "Blanca Libra (500 g)", "500.000", "g", "0601", 2200),
        ("Cosecha Quindío", "Malla 1 kg", "1.000", "kg", "0602", 4100),
        ("Campo Noble", "Roja Peruana Libra (500 g)", "500.000", "g", "0603", 2600),
    ],
    "Ajo": [
        ("Cosecha Quindío", "Malla x 100 g (Cabezas)", "100.000", "g", "0701", 2500),
        ("La Huerta", "Paquete Importado 250 g", "250.000", "g", "0702", 5600),
    ],
    "Papa": [
        ("Cosecha Quindío", "Pastusa Limpia Libra (500 g)", "500.000", "g", "0801", 1600),
        ("Cosecha Quindío", "Pastusa Bolsa 2.5 kg", "2.500", "kg", "0802", 7200),
        ("Cosecha Quindío", "Criolla Amarilla Libra (500 g)", "500.000", "g", "0803", 2800),
    ],
    "Plátano": [
        ("Finca del Café", "Hartón Verde Libra (500 g)", "500.000", "g", "0901", 1500),
        ("Finca del Café", "Hartón Maduro Kilo (1 kg)", "1.000", "kg", "0902", 2900),
    ],
    "Yuca": [
        ("Finca del Café", "Yuca Chirosa Libra (500 g)", "500.000", "g", "1001", 1400),
        ("Finca del Café", "Yuca Parafinada Kilo (1 kg)", "1.000", "kg", "1002", 2600),
    ],
    "Zanahoria": [
        ("Cosecha Quindío", "Zanahoria Fresca Libra (500 g)", "500.000", "g", "1101", 1800),
        ("Cosecha Quindío", "Bolsa Económica 1 kg", "1.000", "kg", "1102", 3300),
    ],
    "Cilantro": [
        ("Huerta Quindiana", "Manojo Fresco 100 g", "100.000", "g", "1201", 1000),
        ("Huerta Quindiana", "Atado Doble 200 g", "200.000", "g", "1202", 1800),
    ],
    "Repollo / Lechuga": [
        ("Huerta Quindiana", "Lechuga Batavia Unidad (400 g)", "400.000", "g", "1301", 2400),
        ("Huerta Quindiana", "Repollo Blanco Libra (500 g)", "500.000", "g", "1302", 1700),
    ],
    "Limón": [
        ("Cosecha Quindío", "Limón Tahití Libra (500 g)", "500.000", "g", "1401", 2000),
        ("Cosecha Quindío", "Malla Limón Tahití 1 kg", "1.000", "kg", "1402", 3700),
    ],
    "Banano": [
        ("Finca del Café", "Banano Criollo Libra (500 g)", "500.000", "g", "1501", 1300),
        ("Finca del Café", "Mano de Banano (1 kg)", "1.000", "kg", "1502", 2400),
    ],
    "Frutas para Jugos": [
        ("Cosecha Quindío", "Guayaba Pera Libra (500 g)", "500.000", "g", "1601", 2100),
        ("Cosecha Quindío", "Mora de Castilla Libra (500 g)", "500.000", "g", "1602", 3400),
        ("Cosecha Quindío", "Papaya Maradol Kilo (1 kg)", "1.000", "kg", "1603", 3800),
    ],
    "Harina de Maíz": [
        ("P.A.N.", "Blanca Precocida Bolsa 1 kg", "1.000", "kg", "1701", 4400),
        ("Doñarepa", "Blanca Precocida Libra 500 g", "500.000", "g", "1702", 2300),
        ("Areparina", "Amarilla Tradicional 1 kg", "1.000", "kg", "1703", 4100),
    ],
    "Avena": [
        ("Quaker", "Avena en Hojuelas Bolsa 400 g", "400.000", "g", "1801", 3900),
        ("Don Pancho", "Avena Molida Bolsa 500 g", "500.000", "g", "1802", 3200),
        ("Quaker", "Avena Familiar 800 g", "800.000", "g", "1803", 7100),
    ],
    "Pan": [
        ("Bimbo", "Pan Tajado Blanco 450 g", "450.000", "g", "1901", 6200),
        ("Comapan", "Pan Tajado Mantequilla 550 g", "550.000", "g", "1902", 6500),
        ("Horno Real", "Pan Tajado Económico 400 g", "400.000", "g", "1903", 4300),
    ],
    "Galletas": [
        ("Noel", "Saltín Noel Tradicional 3 Tacos (300 g)", "300.000", "g", "2001", 4900),
        ("Ducales", "Galletas Ducales Tentación 294 g", "294.000", "g", "2002", 5800),
        ("Saltinas", "Galletas de Soda Paquete 400 g", "400.000", "g", "2003", 4500),
    ],
    "Café": [
        ("Águila Roja", "Café Molido Tradicional 500 g", "500.000", "g", "2101", 15900),
        ("Sello Rojo", "Café Molido Bolsa 250 g", "250.000", "g", "2102", 8200),
        ("Colcafé", "Café Clásico Granulado Frasco 170 g", "170.000", "g", "2103", 16800),
    ],
    "Panela": [
        ("El Trece", "Panela Cuadrada Atado 1 kg (2 und)", "1.000", "kg", "2201", 4800),
        ("La Palestina", "Panela Redonda Libra 500 g", "500.000", "g", "2202", 2500),
        ("Doña Panela", "Panela Pulverizada Bolsa 500 g", "500.000", "g", "2203", 3600),
    ],
    "Chocolate de Mesa": [
        ("Corona", "Chocolate Tradicional Con Azúcar 500 g", "500.000", "g", "2301", 9800),
        ("Luker", "Chocolate de Mesa Tradicional 250 g", "250.000", "g", "2302", 5200),
        ("Sol", "Chocolate de Mesa Familiar 500 g", "500.000", "g", "2303", 9200),
    ],
    "Pollo": [
        ("Mac Pollo", "Pechuga Fresca Bandeja 1 kg", "1.000", "kg", "2401", 14800),
        ("Bucanero", "Pechuga de Pollo Libra (500 g)", "500.000", "g", "2402", 7600),
        ("La Fazenda", "Pernil Contramuslo Bandeja 1 kg", "1.000", "kg", "2403", 10900),
    ],
    "Enlatados de Pescado": [
        ("Van Camp's", "Lomitos de Atún en Aceite 160 g", "160.000", "g", "2501", 6400),
        ("Isabel", "Atún Rallado en Agua 160 g", "160.000", "g", "2502", 4900),
        ("Soberana", "Sardinas en Salsa de Tomate 425 g", "425.000", "g", "2503", 7800),
    ],
    "Queso": [
        ("Colanta", "Queso Campesino Bloque 500 g", "500.000", "g", "2601", 11200),
        ("Alpina", "Queso Doble Crema Tajado 250 g", "250.000", "g", "2602", 8900),
        ("Latti", "Cuajada Fresca Bloque 500 g", "500.000", "g", "2603", 8600),
    ],
    "Mantequilla / Margarina": [
        ("Rama", "Margarina Culinaria Barra 500 g", "500.000", "g", "2701", 6900),
        ("La Fina", "Margarina de Mesa Barra 250 g", "250.000", "g", "2702", 3800),
        ("Colanta", "Mantequilla de Leche con Sal 250 g", "250.000", "g", "2703", 8400),
    ],
    "Especias y Color": [
        ("El Rey", "Color Condimento Sobre 90 g", "90.000", "g", "2801", 2300),
        ("El Rey", "Comino Molido Sobre 50 g", "50.000", "g", "2802", 2100),
        ("Triguisar", "Condimento Completo Sobre 105 g", "105.000", "g", "2803", 2500),
    ],
    "Vinagre": [
        ("La Constancia", "Vinagre Blanco Frasco 500 ml", "500.000", "ml", "2901", 2800),
        ("Bary", "Vinagre de Frutas Botella 1000 ml", "1000.000", "ml", "2902", 4200),
    ],
    "Salsas Básicas": [
        ("Fruco", "Salsa de Tomate Doypack 400 g", "400.000", "g", "3001", 6500),
        ("La Constancia", "Mayonesa Tradicional Doypack 400 g", "400.000", "g", "3002", 6900),
        ("Bary", "Salsa de Tomate Económica 200 g", "200.000", "g", "3003", 3100),
    ],
    "Jabón Lavaloza": [
        ("Axion", "Crema Lavaloza Limón Pote 450 g", "450.000", "g", "3101", 5600),
        ("Loza Crem", "Jabón Lavaloza Líquido 500 ml", "500.000", "ml", "3102", 5200),
        ("Quix", "Lavaloza Líquido Concentrado 750 ml", "750.000", "ml", "3103", 6800),
    ],
    "Detergente para Ropa": [
        ("Fab", "Detergente en Polvo Multiusos 1 kg", "1.000", "kg", "3201", 10800),
        ("Dersa", "Detergente en Polvo Floral 2 kg", "2.000", "kg", "3202", 16900),
        ("Ariel", "Detergente Líquido Concentrado 1.2 L", "1.200", "l", "3203", 21500),
    ],
    "Limpiador de Pisos": [
        ("Fabuloso", "Limpiador Antibacterial Lavanda 1 L", "1.000", "l", "3301", 6900),
        ("Sampic", "Limpiador de Pisos Frutos Rojos 900 ml", "900.000", "ml", "3302", 4800),
        ("Ajax", "Limpiador Bicarbonato Botella 1.8 L", "1.800", "l", "3303", 11200),
    ],
    "Cloro / Límpido": [
        ("Clorox", "Blanqueador Tradicional Botella 1 L", "1.000", "l", "3401", 3900),
        ("Blancox", "Desinfectante Poder Floral 2 L", "2.000", "l", "3402", 6800),
    ],
    "Papel Higiénico": [
        ("Familia", "Papel Higiénico Triple Hoja x 4 und", "4.000", "und", "3501", 7800),
        ("Rosal", "Papel Higiénico Doble Hoja Mega x 12 und", "12.000", "und", "3502", 18900),
        ("Scott", "Rinde Max Doble Hoja x 4 und", "4.000", "und", "3503", 6900),
    ],
    "Jabón de Tocador": [
        ("Protex", "Jabón Antibacterial Avena Barra 110 g", "110.000", "g", "3601", 3800),
        ("Palmolive", "Jabón Naturals Tripack (330 g)", "330.000", "g", "3602", 9600),
        ("Rexona", "Jabón de Tocador Fresh Barra 120 g", "120.000", "g", "3603", 3400),
    ],
    "Crema Dental": [
        ("Colgate", "Triple Acción Tubo 100 ml", "100.000", "ml", "3701", 5900),
        ("Colgate", "Máxima Protección Anticaries 150 ml", "150.000", "ml", "3702", 7900),
        ("Oral-B", "Crema Dental 1-2-3 Tubo 75 ml", "75.000", "ml", "3703", 4300),
    ],
    "Champú": [
        ("Savital", "Champú Sábila y Biotina Frasco 530 ml", "530.000", "ml", "3801", 11900),
        ("Head & Shoulders", "Champú Limpieza Renovadora 375 ml", "375.000", "ml", "3802", 19800),
        ("Pantene", "Champú Restauración Frasco 400 ml", "400.000", "ml", "3803", 17900),
    ],
    "Arroz Blanco de Primera": [
        ("Diana", "Libra 500 g", "500.000", "g", "3901", 2300),
        ("Roa", "Bolsa 1 kg", "1.000", "kg", "3902", 4400),
        ("Diana", "Arroba / Bulto Familiar 2.5 kg", "2.500", "kg", "3903", 10800),
    ],
    "Leche Entera Pasteurizada": [
        ("Colanta", "Bolsa 900 ml", "900.000", "ml", "4001", 4100),
        ("Alquería", "Bolsa Mega 1.1 L", "1.100", "l", "4002", 5200),
    ],
    "Huevo Rojo Tipo AA": [
        ("Avícola del Quindío", "Cubeta x 30 und", "30.000", "und", "4101", 15800),
        ("Santa Reyes", "Medio Panal x 15 und", "15.000", "und", "4102", 8600),
    ],
}


class Command(BaseCommand):
    help = (
        "Puebla 5 usuarios personas naturales (REPORTER), presentaciones derivadas para todos los productos "
        "y cientos de reportes de precios oficiales y comunitarios en Armenia y Quindío."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        del args, options
        now = timezone.now()

        # ------------------------------------------------------------------
        # 1. Crear o sincronizar las 5 Personas Naturales (Rol: REPORTER)
        # ------------------------------------------------------------------
        natural_profiles: list[UserProfile] = []
        created_users = 0

        for idx, person in enumerate(NATURAL_PERSONS):
            user = User.objects.filter(username=person["username"]).first()
            if user is None:
                user = User(
                    id=generate_encoded_entity_id(User, seed_hint=person["email"]),
                    username=person["username"],
                    email=person["email"],
                    first_name=person["first_name"],
                    last_name=person["last_name"],
                    is_active=True,
                )
                user.set_password("Pricecol2026*")
                user.save()
                created_users += 1
            else:
                user.email = person["email"]
                user.first_name = person["first_name"]
                user.last_name = person["last_name"]
                user.set_password("Pricecol2026*")
                user.save()

            update_last_login(None, user)
            # Escalonamos el last_login en las últimas horas para realismo
            User.objects.filter(pk=user.pk).update(
                last_login=now - timedelta(hours=(idx + 1) * 3, minutes=idx * 11)
            )

            profile, prof_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "id": generate_encoded_entity_id(UserProfile, seed_hint=f"profile:{user.id}"),
                    "role": ActorRole.REPORTER,
                    "verification_status": VerificationStatus.UNVERIFIED,
                    "accepted_data_policy": True,
                },
            )
            if not prof_created:
                profile.role = ActorRole.REPORTER
                profile.accepted_data_policy = True
                profile.save(update_fields=["role", "accepted_data_policy"])

            natural_profiles.append(profile)

        self.stdout.write(
            self.style.SUCCESS(
                f"1. Personas naturales listas: {len(natural_profiles)} activas ({created_users} nuevas). "
                f"IDs: {[p.user_id for p in natural_profiles]}"
            )
        )

        # ------------------------------------------------------------------
        # 2. Crear o sincronizar Presentaciones para los 38 Productos
        # ------------------------------------------------------------------
        products = Product.objects.filter(is_active=True).order_by("id")
        presentation_base_price_map: dict[int, int] = {}
        created_presentations = 0
        total_presentations = 0

        for product in products:
            specs = PRODUCT_PRESENTATIONS_CATALOG.get(product.name, [])
            if not specs:
                specs = [
                    ("Genérico", "Presentación Estándar 500 g", "500.000", "g", f"{product.id:02d}99", 3500)
                ]

            for brand, pres_name, qty_str, unit_code, ean_suffix, base_price in specs:
                ean_code = f"77099900{ean_suffix.zfill(4)}"[:12]
                # Dígito de control simple de 13 dígitos
                ean_13 = f"{ean_code}{(sum(int(d) for d in ean_code) % 10)}"

                pres = ProductPresentation.objects.filter(
                    product=product,
                    brand=brand,
                    presentation_name=pres_name,
                ).first()

                if pres is None:
                    # Evitar colisión de EAN si existiera
                    if ProductPresentation.objects.filter(ean_barcode=ean_13).exists():
                        ean_13 = None
                    pres = ProductPresentation.objects.create(
                        product=product,
                        brand=brand,
                        presentation_name=pres_name,
                        quantity=Decimal(qty_str),
                        unit=unit_code,
                        ean_barcode=ean_13,
                        is_active=True,
                    )
                    created_presentations += 1
                else:
                    pres.quantity = Decimal(qty_str)
                    pres.unit = unit_code
                    pres.is_active = True
                    pres.save(update_fields=["quantity", "unit", "is_active"])

                presentation_base_price_map[pres.id] = base_price
                total_presentations += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"2. Presentaciones sincronizadas: {total_presentations} totales ({created_presentations} nuevas)."
            )
        )

        # ------------------------------------------------------------------
        # 3. Poblar Reportes de Precios (Oficiales de Comercio + Personas Naturales)
        # ------------------------------------------------------------------
        establishments = list(
            Establishment.objects.filter(is_active=True)
            .select_related("owner")
            .order_by("id")
        )
        est_by_keyword: dict[str, Establishment] = {}
        for est in establishments:
            est_by_keyword[est.name.lower()] = est

        def find_est(keyword: str, fallback_idx: int = 0) -> Establishment:
            for name_low, est_obj in est_by_keyword.items():
                if keyword in name_low:
                    return est_obj
            return establishments[fallback_idx % len(establishments)]

        est_ara = find_est("ara", 0)
        est_d1 = find_est("d1", 1)
        est_dollarcity = find_est("dollarcity", 2)
        est_carulla = find_est("carulla", 3)
        est_olimpica = find_est("olímpica", 4)
        est_super_inter = find_est("super inter", 5)

        minimarkets = [
            e
            for e in establishments
            if e.establishment_type
            in (
                Establishment.EstablishmentType.MINIMARKET,
                Establishment.EstablishmentType.NEIGHBORHOOD_SHOP,
            )
        ]
        if not minimarkets:
            minimarkets = establishments

        use_case = ReportPriceUseCase()
        all_presentations = list(
            ProductPresentation.objects.filter(is_active=True)
            .select_related("product")
            .order_by("id")
        )

        created_reports_official = 0
        created_reports_community = 0
        created_reports_flagged = 0

        # Factor multiplicador realista según cadena comercial
        # (Hard discounters D1/Ara más económicos, minimercados intermedios, Carulla un poco más alto pero con promos)
        chain_Establishments_factors: list[tuple[Establishment, Decimal, bool]] = [
            (est_d1, Decimal("0.92"), True),
            (est_ara, Decimal("0.94"), True),
            (est_olimpica, Decimal("1.00"), True),
            (est_super_inter, Decimal("0.98"), True),
            (est_carulla, Decimal("1.08"), True),
        ]

        for p_idx, pres in enumerate(all_presentations):
            # Si esta presentación ya tiene >= 4 reportes, no duplicamos innecesariamente
            if PriceReport.objects.filter(presentation=pres).count() >= 4:
                continue

            base_cop = presentation_base_price_map.get(pres.id, 4000)

            # A) 2 Reportes Oficiales de Supermercados Verificados (por su propio dueño `MERCHANT`)
            chain_1, factor_1, _ = chain_Establishments_factors[p_idx % len(chain_Establishments_factors)]
            chain_2, factor_2, _ = chain_Establishments_factors[(p_idx + 2) % len(chain_Establishments_factors)]

            # Si es producto de aseo o abarrotes seleccionados, también incluimos Dollarcity
            if pres.product.category == "PERSONAL_CARE" and p_idx % 2 == 0:
                chain_2 = est_dollarcity
                factor_2 = Decimal("0.95")

            for c_offset, (target_est, price_factor) in enumerate([(chain_1, factor_1), (chain_2, factor_2)]):
                raw_val = (Decimal(base_cop) * price_factor / Decimal(50)).quantize(Decimal(1)) * Decimal(50)
                if raw_val < Decimal(500):
                    raw_val = Decimal("1000.00")

                owner_user = target_est.owner
                if owner_user is not None:
                    merchant_profile, _ = UserProfile.objects.get_or_create(user=owner_user)
                    source_type = resolve_verified_source_type_for_actor(
                        profile=merchant_profile,
                        target_establishment=target_est,
                    )
                    reporter_token = f"user-{owner_user.pk}"
                else:
                    merchant_profile = natural_profiles[0]
                    source_type = resolve_verified_source_type_for_actor(
                        profile=merchant_profile,
                        target_establishment=target_est,
                    )
                    reporter_token = f"user-{merchant_profile.user_id}"

                is_promo = (p_idx + c_offset) % 7 == 0
                promo_desc = "Descuento especial de fin de semana en góndola" if is_promo else ""

                report = use_case.execute(
                    presentation=pres,
                    establishment=target_est,
                    raw_price=raw_val,
                    reporter_token=reporter_token,
                    source_type=source_type,
                    is_promotional=is_promo,
                    promotion_description=promo_desc,
                )
                # Escalonar fecha de reporte entre 4 horas y 72 horas atrás para evitar falso positivo de ráfaga 10m
                backdated_time = now - timedelta(hours=4 + ((p_idx * 3 + c_offset * 5) % 68), minutes=(p_idx * 7) % 59)
                PriceReport.objects.filter(pk=report.pk).update(reported_at=backdated_time)
                report.reported_at = backdated_time

                update_actor_reputation_after_report(
                    profile=merchant_profile,
                    report=report,
                    presentation=pres,
                    establishment=target_est,
                )
                created_reports_official += 1

            # B) 2 Reportes Comunitarios hechos por las 5 Personas Naturales en Minimercados y Supermercados
            for u_offset in range(2):
                citizen_profile = natural_profiles[(p_idx + u_offset) % len(natural_profiles)]
                if u_offset == 0:
                    target_est = minimarkets[(p_idx + u_offset) % len(minimarkets)]
                    # Minimercado de barrio suele variar entre 0.96 y 1.05 del precio base
                    factor = Decimal("0.97") if (p_idx % 3 == 0) else Decimal("1.03")
                else:
                    target_est, factor, _ = chain_Establishments_factors[(p_idx + 1) % len(chain_Establishments_factors)]
                    factor = factor + Decimal("0.02")

                raw_val = (Decimal(base_cop) * factor / Decimal(50)).quantize(Decimal(1)) * Decimal(50)
                if raw_val < Decimal(500):
                    raw_val = Decimal("1000.00")

                source_type = resolve_verified_source_type_for_actor(
                    profile=citizen_profile,
                    target_establishment=target_est,
                )
                is_promo = (p_idx + u_offset) % 9 == 0
                promo_desc = "Precio de cosecha / promoción del día reportada por ciudadano" if is_promo else ""

                report = use_case.execute(
                    presentation=pres,
                    establishment=target_est,
                    raw_price=raw_val,
                    reporter_token=f"user-{citizen_profile.user_id}",
                    source_type=source_type,
                    is_promotional=is_promo,
                    promotion_description=promo_desc,
                )
                backdated_time = now - timedelta(
                    hours=2 + ((p_idx * 2 + u_offset * 7) % 60),
                    minutes=15 + ((p_idx * 11) % 40),
                )
                PriceReport.objects.filter(pk=report.pk).update(reported_at=backdated_time)
                report.reported_at = backdated_time

                update_actor_reputation_after_report(
                    profile=citizen_profile,
                    report=report,
                    presentation=pres,
                    establishment=target_est,
                )
                created_reports_community += 1

        # C) Crear 3 reportes con desviación moderada/alta (LOW_CONFIDENCE / ANOMALOUS)
        # para que el Moderador también tenga casos reales en la bandeja de Moderación
        if PriceReport.objects.filter(reliability_status__in=["LOW_CONFIDENCE", "ANOMALOUS"]).count() < 2:
            for flag_idx, pres in enumerate(all_presentations[:3]):
                citizen_profile = natural_profiles[flag_idx % len(natural_profiles)]
                target_est = minimarkets[flag_idx % len(minimarkets)]
                base_cop = presentation_base_price_map.get(pres.id, 4000)
                # 28% más alto (LOW_CONFIDENCE) o 60% más alto (ANOMALOUS)
                mult = Decimal("1.28") if flag_idx < 2 else Decimal("1.65")
                outlier_price = (Decimal(base_cop) * mult / Decimal(50)).quantize(Decimal(1)) * Decimal(50)

                report = use_case.execute(
                    presentation=pres,
                    establishment=target_est,
                    raw_price=outlier_price,
                    reporter_token=f"user-{citizen_profile.user_id}",
                )
                backdated_time = now - timedelta(hours=1 + flag_idx, minutes=25)
                PriceReport.objects.filter(pk=report.pk).update(reported_at=backdated_time)
                created_reports_flagged += 1

        # Invalidar caché de comparación para todos los productos
        for product in products:
            invalidate_product_comparison_cache(product.id)

        self.stdout.write(
            self.style.SUCCESS(
                f"3. Reportes de precio generados con éxito:\n"
                f"   - Oficiales de comercio (OFFICIAL_MERCHANT): {created_reports_official}\n"
                f"   - Comunitarios de las 5 personas naturales: {created_reports_community}\n"
                f"   - Casos de variación/auditoría para moderador: {created_reports_flagged}\n"
                f"   - Total acumulado en PriceReport: {PriceReport.objects.count()}"
            )
        )
