"""Cross-segment chain, timestamp, and event-id state."""

from timestamp_codec import timestamps_in_order


class ChainTracker:
    def __init__(self):
        self.previous_hash = "0" * 64
        self.last_timestamp = None
        self.seen_event_ids = set()
        self.global_record_index = 0

    def begin_segment(self):
        self.last_timestamp = None
        self.seen_event_ids = set()

    def is_genesis_record(self):
        return self.global_record_index == 0

    def check_chain(self, previous_hash):
        return previous_hash == self.previous_hash

    def advance_chain(self, record_hash):
        self.previous_hash = record_hash
        self.global_record_index += 1

    def check_timestamp(self, timestamp):
        return timestamps_in_order(self.last_timestamp, timestamp)

    def advance_timestamp(self, timestamp):
        self.last_timestamp = timestamp

    def is_duplicate(self, event_id):
        return event_id in self.seen_event_ids

    def register_event_id(self, event_id):
        self.seen_event_ids.add(event_id)
