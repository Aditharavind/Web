"""Input models should reject malformed fields before persistence."""

import pytest
from pydantic import ValidationError

from app.models.schemas import ProductCreate, ProductUpdate


@pytest.mark.parametrize("model", [ProductCreate, ProductUpdate])
def test_product_text_normalization(model):
    product = model(
        name=" Valve ",
        category=" Flow control ",
        description=None,
        tags=" MRO ",
        specs=[" Pressure: 10 bar ", " "],
    )
    assert product.name == "Valve"
    assert product.category == "Flow control"
    assert product.description == ""
    assert product.tags == "MRO"
    assert product.specs == ["Pressure: 10 bar"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", {}),
        ("name", " "),
        ("category", 123),
        ("description", []),
        ("tags", False),
        ("specs", [None]),
        ("specs", [{"invalid": "row"}]),
        ("specs", "row"),
        ("specs", ["x" * 4001]),
        ("specs", ["row"] * 51),
    ],
)
@pytest.mark.parametrize("model", [ProductCreate, ProductUpdate])
def test_product_invalid_fields(model, field, value):
    data = {"name": "Valve", "category": "Oilfield", field: value}
    with pytest.raises(ValidationError):
        model(**data)


def test_specification_boundary_and_independent_defaults():
    first = ProductCreate(name="Valve", category="Oilfield", specs=["x" * 4000] * 50)
    assert len(first.specs) == 50
    second = ProductCreate(name="Pump", category="Oilfield")
    third = ProductCreate(name="Seal", category="Oilfield")
    second.specs.append("Size: 10 mm")
    assert third.specs == []


def test_search_keywords_allow_long_lists_but_stay_bounded():
    from app.models.schemas import MAX_TAGS_LENGTH

    long_keywords = ", ".join(f"keyword {n}" for n in range(150))
    assert 255 < len(long_keywords) <= MAX_TAGS_LENGTH
    assert ProductCreate(name="Valve", category="Tools", tags=long_keywords).tags == long_keywords
    with pytest.raises(ValidationError):
        ProductCreate(name="Valve", category="Tools", tags="x" * (MAX_TAGS_LENGTH + 1))
