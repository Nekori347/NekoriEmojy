"""Tag semantics: a global library metadatum projected onto one location.

A tag is not a category. Resources carry tags, no node owns a tag, and the
panel only ever shows a projection of the tags that the resources of the
*effective* location actually use -- so a tag used only inside Folder2 does not
appear while the user is standing in Folder1.

The manual tag order is global and has exactly one copy. Filtering the
projection therefore never reorders anything: the panel always reads the same
single order, and a block move writes back into it while every tag the
projection left out keeps its relative position.

OCR text is deliberately absent. `ocr_text` and any future user-corrected OCR
text are search metadata only: they never become a tag, never appear here and
never take part in tag ordering.
"""
from fluent_ui.components.drop_contract import INSERT_AFTER, INSERT_BEFORE

# Why a rename / create was refused; the panel turns these into messages.
EMPTY = 'empty'
SPACE = 'space'
EXISTS = 'exists'


class TagItem:
    """One tag as the panel needs it: identity and current usage count."""

    __slots__ = ('name', 'count')

    def __init__(self, name, count=0):
        self.name = name
        self.count = count

    def __eq__(self, other):
        return isinstance(other, TagItem) and (self.name, self.count) == (other.name, other.count)

    def __repr__(self):
        return f"TagItem({self.name!r}, {self.count})"


class TagModel:
    """Data and rules for tags; nothing here knows how a panel looks."""

    def __init__(self, storage):
        self.storage = storage
        self._order = list(storage.tag_order())
        self._visible = []

    # -- the single global order ---------------------------------------
    def order(self):
        return list(self._order)

    def visible(self):
        return list(self._visible)

    def reload(self):
        self._order = list(self.storage.tag_order())

    def _register(self, names):
        """Tags that exist on resources but not in the order join its end.

        This keeps the order a superset of every tag in the library without a
        migration: a library written before tags had an order simply grows one.
        """
        missing = sorted({name for name in names if name and name not in self._order},
                         key=str.casefold)
        if missing:
            self._order.extend(missing)
            self._persist()

    def _persist(self):
        self.storage.set_tag_order(self._order)

    @staticmethod
    def validate(name):
        name = (name or '').strip()
        if not name:
            return EMPTY
        # Tags are stored space-separated on the resource, so a name that
        # contains a space could not survive a round trip.
        if any(ch.isspace() for ch in name):
            return SPACE
        return None

    # -- projection ----------------------------------------------------
    def project(self, node_id=None, resource_ids=None, tag_texts=None):
        """The ordered tags the effective location uses, plus idle tags.

        `tag_texts` is tag text already in hand (a search result set carries
        it), otherwise `node_id` is counted as a whole subtree. A tag that no
        resource anywhere uses carries no location, so it stays visible in
        every location -- that is what makes a freshly created tag usable
        instead of vanishing the moment it is created.
        """
        if tag_texts is not None:
            counts = self.storage.count_tags(tag_texts)
        else:
            counts = self.storage.tag_usage(node_id=node_id, resource_ids=resource_ids)
        self._register(counts)
        idle = {name for name in self._order if name not in counts}
        if idle:
            library = self.storage.tag_usage()
            idle = {name for name in idle if not library.get(name)}
        items = [TagItem(name, counts.get(name, 0)) for name in self._order
                 if name in counts or name in idle]
        self._visible = [item.name for item in items]
        return items

    def names(self):
        return list(self._order)

    # -- mutations -----------------------------------------------------
    def create(self, name):
        """Create a global tag. Never a child of the current category."""
        reason = self.validate(name)
        if reason:
            return reason
        name = name.strip()
        if name in self._order:
            return EXISTS
        self._order.append(name)
        self._persist()
        return None

    def rename(self, old, new):
        reason = self.validate(new)
        if reason:
            return reason
        new = new.strip()
        if new == old:
            return None
        if new in self._order:
            return EXISTS
        self.storage.rename_tag(old, new)
        renamed = [new if name == old else name for name in self._order]
        if new not in renamed:
            renamed.append(new)
        self._order = list(dict.fromkeys(renamed))
        self._persist()
        return None

    def delete(self, names):
        """Remove the tag relation from every resource; files stay untouched."""
        names = [name for name in names if name]
        removed = self.storage.delete_tags(names)
        self._order = [name for name in self._order if name not in set(names)]
        self._persist()
        return removed

    def reorder(self, moving, target=None, placement=INSERT_BEFORE):
        """Move a whole block inside the single global order.

        Only the block moves. Tags the projection filtered out keep their
        relative order, and a block dropped at the end of the visible list
        lands right after the last visible tag instead of jumping past every
        hidden one. The block itself keeps its internal order.
        """
        from services.manual_order import selection_block, insertion_position, insert_block
        moving = selection_block(self._order, moving)
        if not moving:
            return False
        if target in moving:
            return False
        rest = [name for name in self._order if name not in set(moving)]
        index = insertion_position(self._order, moving, target, placement == INSERT_AFTER, self._visible)
        self._order = insert_block(rest, moving, index)
        self._persist()
        return True
