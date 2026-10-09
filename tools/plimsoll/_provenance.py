"""Dependency metadata shared by selected-ledger projections and kernels."""
import copy


def combine_estimates(values):
    """True dominates unknown; only a nonempty set of all False is exact."""
    flags = list(values)
    if any(value is True for value in flags):
        return True
    return False if flags and all(value is False for value in flags) else None


def field_metadata(item, field):
    """Prefer the selected field's provenance over unrelated item fields."""
    provenance = item.get('provenance') or {}
    fields = provenance.get('fields') or {}
    return fields.get(field, provenance or item)


def unique_sources(values):
    """Preserve structured sources and their declaration order without mutation."""
    result = []
    for value in values:
        known = isinstance(value, dict) and bool(value) or isinstance(value, str) and bool(value.strip())
        if known and value not in result:
            result.append(copy.deepcopy(value))
    return result or None
