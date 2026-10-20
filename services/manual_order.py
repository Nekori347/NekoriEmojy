"""Canonical insertion of a stable selection block after its removal."""


def selection_block(order, selected, parents=None):
    wanted = set(selected)
    def covered(key):
        seen = set()
        parent = (parents or {}).get(key)
        while parent is not None and parent not in seen:
            if parent in wanted:
                return True
            seen.add(parent)
            parent = (parents or {}).get(parent)
        return False
    return [key for key in order if key in wanted and not covered(key)]


def insertion_position(order, moving, target=None, after=False, visible=None):
    """Resolve a stable anchor in canonical order after removing the block."""
    remaining = [key for key in order if key not in set(moving)]
    if target in remaining:
        return remaining.index(target) + int(after)
    if visible is not None:
        tail = [key for key in visible if key in remaining]
        return remaining.index(tail[-1])+1 if tail else 0
    return len(remaining)


def insert_block(remaining, moving, position=None):
    values = list(remaining)
    slot = len(values) if position is None else max(0, min(position, len(values)))
    values[slot:slot] = list(moving)
    return values
