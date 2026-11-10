"""
Comando `python manage.py seed_products_catalog`:
Puebla la tabla de Productos base (moldes genéricos) de la canasta familiar colombiana / quindiana,
estructurados según la taxonomía oficial de Pricecol (PERISHABLE, GROCERY, PERSONAL_CARE)
con sus sinónimos y descripciones de dominio (Pregunta 4 de la Guía y Sección 4.2).
"""

from django.core.management.base import BaseCommand

from catalog.models import Product
from core_domain.entities import ProductCategory


class Command(BaseCommand):
    help = "Puebla el catálogo de productos base (moldes) de la canasta familiar sin quemar presentaciones derivadas."

    def handle(self, *args, **options) -> None:
        del args, options
        self.stdout.write("Poblando moldes de productos base en Pricecol...")

        products_data = [
            # ==========================================
            # 1. FRUTAS, VERDURAS Y TUBÉRCULOS (PERISHABLE)
            # ==========================================
            # Base para guisos (hogao)
            {
                "name": "Tomate Chonto",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "tomate, tomate de guiso, tomate chonto, tomate aliño",
                "description": "Tomate chonto fresco para guiso, ensaladas y consumo diario en los hogares.",
            },
            {
                "name": "Cebolla Larga / Junca",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "cebolla larga, cebolla junca, cebolla de rama, cebolla verde",
                "description": "Cebolla junca o larga fresca, base fundamental para el tradicional hogao.",
            },
            {
                "name": "Cebolla Cabezona",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "cebolla cabezona, cebolla blanca, cebolla roja",
                "description": "Cebolla cabezona fresca para cocina diaria y aderezos.",
            },
            {
                "name": "Ajo",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "ajo, cabeza de ajo, dientes de ajo",
                "description": "Ajo fresco en cabeza o malla para sazón y preparaciones culinarias.",
            },
            # Tubérculos y complementos
            {
                "name": "Papa",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "papa, papa pastusa, papa criolla, papa parda, papa nevada",
                "description": "Papa fresca en sus variedades pastusa, criolla o común para sopas y guisos.",
            },
            {
                "name": "Plátano",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "platano, platano verde, platano maduro, platano guineo",
                "description": "Plátano verde o maduro de alta demanda en la región cafetera.",
            },
            {
                "name": "Yuca",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "yuca, yuca fresca, yuca llanera, yuca chiroza",
                "description": "Yuca fresca para cocidos, caldos y fritos tradicionales.",
            },
            # Verduras básicas
            {
                "name": "Zanahoria",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "zanahoria, zanahoria fresca",
                "description": "Zanahoria fresca para ensaladas, sopas y jugos.",
            },
            {
                "name": "Cilantro",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "cilantro, atado de cilantro, cilantro de castilla",
                "description": "Cilantro fresco aromático para caldos, sopas y aderezos.",
            },
            {
                "name": "Repollo / Lechuga",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "repollo, lechuga, repollo blanco, repollo morado, lechuga batavia",
                "description": "Hortalizas de hoja verde para ensaladas y guarniciones familiares.",
            },
            # Frutas de alto consumo
            {
                "name": "Limón",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "limon, limon tahiti, limon comun, limon mandarino",
                "description": "Limón fresco para bebidas, jugos y condimento de comidas.",
            },
            {
                "name": "Banano",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "banano, platano banano, guineo maduro",
                "description": "Banano dulce de alto consumo calórico y nutricional.",
            },
            {
                "name": "Frutas para Jugos",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "guayaba, papaya, mora, lulo, maracuya, pulpa de fruta",
                "description": "Frutas tradicionales de cosecha para preparación de jugos caseros.",
            },

            # ==========================================
            # 2. HARINAS, CEREALES Y PANADERÍA (GROCERY)
            # ==========================================
            {
                "name": "Harina de Maíz",
                "category": ProductCategory.GROCERY.value,
                "aliases": "harina de maiz, harina para arepas, maiz blanco, maiz amarillo",
                "description": "Harina de maíz precocida indispensable para arepas y masas.",
            },
            {
                "name": "Avena",
                "category": ProductCategory.GROCERY.value,
                "aliases": "avena, avena en hojuelas, avena molida",
                "description": "Avena en hojuelas o molida para desayunos y batidos nutritivos.",
            },
            {
                "name": "Pan",
                "category": ProductCategory.GROCERY.value,
                "aliases": "pan, pan tajado, pan bimbo, pan de molde, pan artesanal",
                "description": "Pan tajado o tradicional para desayunos y meriendas familiares.",
            },
            {
                "name": "Galletas",
                "category": ProductCategory.GROCERY.value,
                "aliases": "galletas, galletas saltin, galletas de sal, galletas dulces",
                "description": "Galletas de sal o dulces para loncheras y acompañamientos.",
            },

            # ==========================================
            # 3. BEBIDAS (GROCERY)
            # ==========================================
            {
                "name": "Café",
                "category": ProductCategory.GROCERY.value,
                "aliases": "cafe, cafe molido, cafe tostado, cafe instantaneo, cafe sello rojo",
                "description": "Café tostado y molido, producto insignia del Quindío y canasta familiar.",
            },
            {
                "name": "Panela",
                "category": ProductCategory.GROCERY.value,
                "aliases": "panela, panela redonda, panela cuadrada, panela pastilla, aguapanela",
                "description": "Panela de caña tradicional para aguapanela y endulzar bebidas.",
            },
            {
                "name": "Chocolate de Mesa",
                "category": ProductCategory.GROCERY.value,
                "aliases": "chocolate, chocolate de mesa, pastillas de chocolate, chocolate tradicional, chocolyne",
                "description": "Pastillas de chocolate para hervir y batir al desayuno.",
            },

            # ==========================================
            # 4. OTRAS PROTEÍNAS Y LÁCTEOS
            # ==========================================
            {
                "name": "Pollo",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "pollo, pechuga, pierna pernil, menudencias, pollo entero",
                "description": "Pollo fresco en presas o entero como proteína accesible de la canasta.",
            },
            {
                "name": "Enlatados de Pescado",
                "category": ProductCategory.GROCERY.value,
                "aliases": "atun, sardinas, lata de atun, atun en agua, atun en aceite, sardinas en tomate",
                "description": "Atún o sardinas enlatadas de larga conservación.",
            },
            {
                "name": "Queso",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "queso, queso campesino, cuajada, queso doble crema, quesito",
                "description": "Queso campesino, cuajada o doble crema para consumo diario.",
            },
            {
                "name": "Mantequilla / Margarina",
                "category": ProductCategory.GROCERY.value,
                "aliases": "mantequilla, margarina, margarina de mesa, mantequilla de vaca",
                "description": "Mantequilla o margarina de mesa para untar y freír.",
            },

            # ==========================================
            # 5. CONDIMENTOS Y EXTRAS (GROCERY)
            # ==========================================
            {
                "name": "Especias y Color",
                "category": ProductCategory.GROCERY.value,
                "aliases": "color, achiote, comino, pimienta, condimento completo, triguisar",
                "description": "Condimentos básicos en polvo (color, comino, pimienta) para sazonar.",
            },
            {
                "name": "Vinagre",
                "category": ProductCategory.GROCERY.value,
                "aliases": "vinagre, vinagre blanco, vinagre de manzana, vinagre frutal",
                "description": "Vinagre blanco o frutal para cocina, aderezos y desinfección de alimentos.",
            },
            {
                "name": "Salsas Básicas",
                "category": ProductCategory.GROCERY.value,
                "aliases": "salsa de tomate, mayonesa, mostaza, salsa tártara, salsa bbq",
                "description": "Aderezos y salsas en doypack o frasco para acompañar alimentos.",
            },

            # ==========================================
            # 6. ASEO DEL HOGAR Y PERSONAL (PERSONAL_CARE)
            # ==========================================
            # Hogar
            {
                "name": "Jabón Lavaloza",
                "category": ProductCategory.PERSONAL_CARE.value,
                "aliases": "lavaloza, jabon lavaplatos, axion, crema lavaloza, lavaloza liquido",
                "description": "Jabón lavaplatos en crema o líquido para desengrasar vajillas.",
            },
            {
                "name": "Detergente para Ropa",
                "category": ProductCategory.PERSONAL_CARE.value,
                "aliases": "detergente, jabon en polvo, jabon liquido ropa, ariel, fab, derrite",
                "description": "Detergente en polvo o líquido para lavado de prendas textiles.",
            },
            {
                "name": "Limpiador de Pisos",
                "category": ProductCategory.PERSONAL_CARE.value,
                "aliases": "limpiador de pisos, desinfectante, fabuloso, limpiapisos",
                "description": "Limpiador aromatizante y desinfectante para superficies y pisos.",
            },
            {
                "name": "Cloro / Límpido",
                "category": ProductCategory.PERSONAL_CARE.value,
                "aliases": "limpido, cloro, blanqueador, hipoclorito, clorox",
                "description": "Blanqueador y desinfectante clorado para el hogar.",
            },
            # Personal
            {
                "name": "Papel Higiénico",
                "category": ProductCategory.PERSONAL_CARE.value,
                "aliases": "papel higienico, rollo de papel, papel de baño, papel familia",
                "description": "Papel higiénico suave de doble o triple hoja.",
            },
            {
                "name": "Jabón de Tocador",
                "category": ProductCategory.PERSONAL_CARE.value,
                "aliases": "jabon de tocador, jabon de baño, barra de jabon, jabon palmolive, jabon dove",
                "description": "Jabón en barra o líquido para higiene corporal diaria.",
            },
            {
                "name": "Crema Dental",
                "category": ProductCategory.PERSONAL_CARE.value,
                "aliases": "crema dental, pasta de dientes, colgate, crema colgate, dentifrico",
                "description": "Pasta o crema dental con flúor para cuidado bucal.",
            },
            {
                "name": "Champú",
                "category": ProductCategory.PERSONAL_CARE.value,
                "aliases": "champu, shampoo, champoo, sedal, pantene, h&s",
                "description": "Champú para limpieza y cuidado capilar personal.",
            },
        ]

        created_count = 0
        updated_count = 0

        for item in products_data:
            prod, created = Product.objects.update_or_create(
                name=item["name"],
                defaults={
                    "category": item["category"],
                    "aliases": item["aliases"],
                    "description": item["description"],
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f" [+] Creado Molde: {prod.name} [{prod.category}]"))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f" [*] Actualizado: {prod.name} [{prod.category}]"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCatálogo de moldes poblado con éxito: {created_count} creados, {updated_count} actualizados."
            )
        )
