from django.db import migrations


CATEGORIES_DATA = [
    {
        "code": "FRUITS_VEGGIES",
        "name": "Frutas y Verduras",
        "volatility": "high",
        "color": "sky",
        "description": "Frutas, verduras, hortalizas y tubérculos frescos de alta rotación.",
        "display_order": 1,
        "is_active": True,
    },
    {
        "code": "PERISHABLE",
        "name": "Perecederos y Frescos",
        "volatility": "high",
        "color": "sky",
        "description": "Carnes, pollo, lácteos, huevos y alimentos frescos refrigerados.",
        "display_order": 2,
        "is_active": True,
    },
    {
        "code": "GROCERY",
        "name": "Granos y Abarrotes",
        "volatility": "low",
        "color": "aqua",
        "description": "Arroz, cereales, café, panela, harinas, aceites y despensa seca.",
        "display_order": 3,
        "is_active": True,
    },
    {
        "code": "BEVERAGES",
        "name": "Bebidas y Licores",
        "volatility": "low",
        "color": "lilac",
        "description": "Gaseosas, jugos envasados, cervezas, licores y agua envasada.",
        "display_order": 4,
        "is_active": True,
    },
    {
        "code": "PERSONAL_CARE",
        "name": "Cuidado Personal",
        "volatility": "low",
        "color": "blush",
        "description": "Higiene personal, jabón de tocador, champú y cuidado bucal.",
        "display_order": 5,
        "is_active": True,
    },
    {
        "code": "CLEANING",
        "name": "Limpieza del Hogar",
        "volatility": "low",
        "color": "blush",
        "description": "Detergentes, lavaloza, blanqueadores, desinfectantes y aseo doméstico.",
        "display_order": 6,
        "is_active": True,
    },
]

# Mapeo exacto de nombres de productos a su nueva categoría
RECLASSIFICATION_MAP = {
    # 1. FRUITS_VEGGIES (Frutas y Verduras)
    "Tomate Chonto": "FRUITS_VEGGIES",
    "Cebolla Larga / Junca": "FRUITS_VEGGIES",
    "Cebolla Cabezona": "FRUITS_VEGGIES",
    "Ajo": "FRUITS_VEGGIES",
    "Papa": "FRUITS_VEGGIES",
    "Plátano": "FRUITS_VEGGIES",
    "Yuca": "FRUITS_VEGGIES",
    "Zanahoria": "FRUITS_VEGGIES",
    "Cilantro": "FRUITS_VEGGIES",
    "Repollo / Lechuga": "FRUITS_VEGGIES",
    "Limón": "FRUITS_VEGGIES",
    "Banano": "FRUITS_VEGGIES",
    "Frutas para Jugos": "FRUITS_VEGGIES",

    # 2. CLEANING (Limpieza del Hogar)
    "Jabón Lavaloza": "CLEANING",
    "Detergente para Ropa": "CLEANING",
    "Limpiador de Pisos": "CLEANING",
    "Cloro / Límpido": "CLEANING",

    # 3. PERSONAL_CARE (Cuidado Personal)
    "Papel Higiénico": "PERSONAL_CARE",
    "Jabón de Tocador": "PERSONAL_CARE",
    "Crema Dental": "PERSONAL_CARE",
    "Champú": "PERSONAL_CARE",

    # 4. PERISHABLE (Perecederos de origen animal)
    "Leche Entera Pasteurizada": "PERISHABLE",
    "Huevo Rojo Tipo AA": "PERISHABLE",
    "Pollo": "PERISHABLE",
    "Queso": "PERISHABLE",

    # 5. GROCERY (Granos y Abarrotes)
    "Arroz Blanco de Primera": "GROCERY",
    "Harina de Maíz": "GROCERY",
    "Avena": "GROCERY",
    "Pan": "GROCERY",
    "Galletas": "GROCERY",
    "Café": "GROCERY",
    "Panela": "GROCERY",
    "Chocolate de Mesa": "GROCERY",
    "Enlatados de Pescado": "GROCERY",
    "Mantequilla / Margarina": "GROCERY",
    "Especias y Color": "GROCERY",
    "Vinagre": "GROCERY",
    "Salsas Básicas": "GROCERY",
}


def populate_and_reclassify(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Product = apps.get_model("catalog", "Product")

    # 1. Crear o actualizar las 6 categorías canónicas
    for cat in CATEGORIES_DATA:
        Category.objects.update_or_create(
            code=cat["code"],
            defaults={
                "name": cat["name"],
                "volatility": cat["volatility"],
                "color": cat["color"],
                "description": cat["description"],
                "display_order": cat["display_order"],
                "is_active": cat["is_active"],
            },
        )

    # 2. Reclasificar los productos existentes según la taxonomía oficial de 6 categorías
    for product_name, new_category in RECLASSIFICATION_MAP.items():
        Product.objects.filter(name__iexact=product_name).update(category=new_category)


def reverse_populate_and_reclassify(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")

    # Revertir productos FRUITS_VEGGIES a PERISHABLE y CLEANING a PERSONAL_CARE
    Product.objects.filter(category="FRUITS_VEGGIES").update(category="PERISHABLE")
    Product.objects.filter(category="CLEANING").update(category="PERSONAL_CARE")


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0007_category_alter_product_category"),
    ]

    operations = [
        migrations.RunPython(populate_and_reclassify, reverse_populate_and_reclassify),
    ]
