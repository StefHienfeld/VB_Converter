# hienfeld/domain/cluster.py
"""
Domain model for a cluster of similar clauses.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from .clause import Clause


@dataclass
class Cluster:
    """
    Represents a group of similar clauses identified by the Leader algorithm.
    
    Attributes:
        id: Unique cluster identifier (e.g., "CL-0001")
        leader_clause: The representative clause for this cluster
        member_ids: List of clause IDs belonging to this cluster
        frequency: Number of clauses in this cluster
        name: Human-readable descriptive name
    """
    id: str
    leader_clause: Clause
    member_ids: List[str] = field(default_factory=list)
    frequency: int = 0
    name: str = ""
    
    def __post_init__(self):
        """Initialize frequency if not set."""
        if self.frequency == 0:
            self.frequency = len(self.member_ids) + 1  # +1 for leader
    
    def add_member(self, clause_id: str) -> None:
        """Add a clause to this cluster."""
        if clause_id not in self.member_ids:
            self.member_ids.append(clause_id)
            self.frequency = len(self.member_ids) + 1
    
    @property
    def leader_text(self) -> str:
        """Get the simplified text of the leader clause."""
        return self.leader_clause.simplified_text
    
    @property
    def original_text(self) -> str:
        """Get the original text of the leader clause."""
        return self.leader_clause.raw_text

