import pytest
from datetime import datetime
from project_builder.database.timeline import generate_timeline_event_id, reset_counters_for_testing

def test_timeline_event_id_determinism():
    """
    Verify that generate_timeline_event_id returns the exact same string 
    when called twice with identical arguments, assuming the counter state is managed.
    """
    mid = "m1"
    tid = "t1"
    event_type = "test_event"
    created_at = datetime(2023, 1, 1, 12, 0, 0)
    
    # Reset counter
    reset_counters_for_testing()
    
    # First call: counter becomes 1
    id1 = generate_timeline_event_id(mid, tid, event_type, created_at)
    
    # Reset counter to simulate "same state"
    reset_counters_for_testing()
    
    # Second call: counter becomes 1 again
    id2 = generate_timeline_event_id(mid, tid, event_type, created_at)
    
    assert id1 == id2, "IDs should be identical for same inputs and counter state"

def test_timeline_event_id_uniqueness_sequential():
    """Verify that sequential calls produce different IDs due to counter increment."""
    mid = "m1"
    tid = "t2"
    event_type = "test_event"
    created_at = datetime(2023, 1, 1, 12, 0, 0)
    
    # Reset counter
    reset_counters_for_testing()
    
    id1 = generate_timeline_event_id(mid, tid, event_type, created_at)
    id2 = generate_timeline_event_id(mid, tid, event_type, created_at)
    
    assert id1 != id2, "Sequential IDs must differ"
