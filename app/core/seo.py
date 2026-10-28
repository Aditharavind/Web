"""Search-engine titles, descriptions and structured data, built only from stored product data.

Nothing here invents facts: no prices, offers, ratings, reviews, availability, brands or
specifications. Every product is quote-only, so the Product schema deliberately has no
`offers`; Google reports that as an optional warning, which is the honest alternative to
publishing made-up commercial data.
"""

from __future__ import annotations

from app.models.schemas import Product

COMPANY = "NAWA Global"
SHORT_DESCRIPTION_LENGTH = 80  # shorter product descriptions give search engines little to index
_META_LIMIT = 158
_TITLE_LIMIT = 66


def truncate(text: str, limit: int) -> str:
    """Cut at a word boundary and add an ellipsis, so a snippet never ends mid-word."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:.-/ ")
    return f"{cut}…"


def has_short_description(product: Product) -> bool:
    return len(" ".join(product.description.split())) < SHORT_DESCRIPTION_LENGTH


def product_title(product: Product) -> str:
    """`Name | Category | NAWA Global` when it fits, so similar products stay distinguishable."""
    name = " ".join(product.name.split())
    category = " ".join(product.category.split())
    for candidate in (f"{name} | {category} | {COMPANY}" if category else "", f"{name} | {COMPANY}"):
        if candidate and len(candidate) <= _TITLE_LIMIT:
            return candidate
    return f"{truncate(name, _TITLE_LIMIT - len(COMPANY) - 3)} | {COMPANY}"


def product_description(product: Product) -> str:
    """Meta description: the real description when it is substantial, otherwise real facts."""
    text = " ".join(product.description.split())
    if len(text) >= SHORT_DESCRIPTION_LENGTH:
        return truncate(text, _META_LIMIT)
    sentences = [text.rstrip(".") if text else product.name]
    if product.category and product.category.lower() not in sentences[0].lower():
        sentences.append(f"Category: {product.category}")
    specs = [spec for spec in product.specs[:2] if ":" in spec]
    if specs:
        sentences.append("; ".join(specs))
    sentences.append(f"Request a quote from {COMPANY}, Abu Dhabi")
    return truncate(". ".join(sentences) + ".", _META_LIMIT)


def _spec_properties(specs: list[str]) -> list[dict[str, str]]:
    properties = []
    for spec in specs:
        label, separator, value = spec.partition(":")
        if separator and label.strip() and value.strip():
            properties.append(
                {"@type": "PropertyValue", "name": label.strip(), "value": value.strip()}
            )
    return properties


def product_structured_data(
    product: Product,
    *,
    canonical: str,
    image_urls: list[str],
    home_url: str,
    catalog_url: str,
) -> list[dict[str, object]]:
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": home_url},
            {"@type": "ListItem", "position": 2, "name": "Products", "item": catalog_url},
            {"@type": "ListItem", "position": 3, "name": product.name, "item": canonical},
        ],
    }
    record: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "@id": f"{canonical}#product",
        "name": product.name,
        "description": product_description(product) if has_short_description(product) else product.description,
        "category": product.category,
        "image": image_urls,
        "url": canonical,
        "mainEntityOfPage": canonical,
    }
    if product.tags:
        record["keywords"] = product.tags
    properties = _spec_properties(product.specs)
    if properties:
        record["additionalProperty"] = properties
    return [breadcrumbs, record]


def catalog_seo(
    categories: list[str], query: str, page: int, total: int
) -> tuple[str, str, str]:
    """(title, description, robots) for the product listing and its filtered variants."""
    if len(categories) == 1:
        subject = categories[0]
        noun = "" if subject.lower().endswith(("products", "supplies", "equipment")) else " Products"
        title = f"{subject}{noun} in UAE | {COMPANY}"
        description = (
            f"Browse {subject} from {COMPANY} in Mussafah, Abu Dhabi, UAE. "
            "Request a quote on WhatsApp or email."
        )
    else:
        title = f"Oilfield & Industrial Products in UAE | {COMPANY}"
        description = (
            "Oilfield equipment, valves and fittings, MRO supplies, lubricants and industrial "
            f"safety products from {COMPANY}, Mussafah, Abu Dhabi. Request a quote."
        )
    if page > 1:
        title = f"{title.rsplit(' | ', 1)[0]} - Page {page} | {COMPANY}"
        description = f"Page {page}. {description}"
    # Free-text searches, combined filters and empty lists are not pages worth indexing.
    index = not query and len(categories) <= 1 and total > 0
    return title, truncate(description, _META_LIMIT), "index,follow" if index else "noindex,follow"
