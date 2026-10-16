"""Resource presentation order; nodes remain structural run boundaries."""
from enum import Enum


class ResourceSort(str, Enum):
    MANUAL = 'manual'
    RECENT_ADDED = 'recent_added'
    OLDEST_ADDED = 'oldest_added'

    def project(self, entries):
        if self == self.MANUAL:
            return entries
        result, run = [], []

        def flush():
            result.extend(sorted(run, key=lambda e: e['resource']['library_added_seq'],
                                 reverse=self == self.RECENT_ADDED))
            run.clear()

        for entry in entries:
            if entry['kind'] == 'resource':
                run.append(entry)
            else:
                flush()
                result.append(entry)
        flush()
        return result
