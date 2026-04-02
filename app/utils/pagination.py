from __future__ import annotations


def build_pagination(page: int, total_pages: int) -> list[dict[str, int | str | bool]]:
    if total_pages <= 1:
        return []

    pages: list[dict[str, int | str | bool]] = []
    visible_pages = {1, total_pages, *range(max(1, page - 2), min(total_pages + 1, page + 3))}
    previous = None

    for current in sorted(visible_pages):
        if previous and current - previous > 1:
            pages.append({"kind": "ellipsis", "value": "..."})
        pages.append(
            {
                "kind": "page",
                "value": current,
                "active": current == page,
            }
        )
        previous = current

    return pages
