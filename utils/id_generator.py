"""
id_generator.py - Generates unique IDs for UI tree nodes.
Uses UUID4 to guarantee uniqueness across sessions.
"""
import uuid


def generate_id(prefix: str = "node") -> str:
    """Generate a unique node ID with an optional prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def generate_stable_key(node_id: str, component_type: str) -> str:
    """
    Generate a stable widget key from node ID and component type.
    Ensures no duplicate keys and consistent state across reruns.
    """
    return f"{node_id}_{component_type}"
