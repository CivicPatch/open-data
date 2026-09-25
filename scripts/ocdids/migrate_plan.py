"""Plan moving a state's stored OCD-IDs to their assigned ones (pure — no I/O)."""

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict

from scripts.ocdids.ids import Rewrite, rewrite_ocdid, rewrites_for, to_jurisdiction_ocdid
from scripts.ocdids.models import Assignment
from scripts.ocdids.parse import jurisdiction_ocdid_to_folder, jurisdiction_to_file
from scripts.ocdids.stored import Level, StoredJurisdiction
from scripts.paths import PROJECT_ROOT


class Move(BaseModel):
    model_config = ConfigDict(frozen=True)

    geoid: str
    level: Level
    old_id: str
    new_id: str
    ambiguous: bool  # old_id was shared with another entry, so files under it can't be attributed


class Rename(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: Path
    target: Path


class MigrationPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: str
    moves: Tuple[Move, ...]
    rewrites: Tuple[Rewrite, ...]  # longest prefix first
    renames: Tuple[Rename, ...]    # candidates; not all sources exist on disk
    collisions: Tuple[str, ...]

    @property
    def new_id_by_geoid(self) -> Dict[str, str]:
        return {move.geoid: move.new_id for move in self.moves}


def plan_migration(state: str, stored: Sequence[StoredJurisdiction], assignments: Mapping[str, Assignment]) -> MigrationPlan:
    moves = find_moves(stored, assignments)
    unambiguous = [move for move in moves if not move.ambiguous]

    renames = []
    for move in unambiguous:
        if move.level == Level.LOCAL:
            renames.extend(renames_for(move))

    return MigrationPlan(
        state=state,
        moves=tuple(moves),
        rewrites=rewrites_longest_first(unambiguous),
        renames=tuple(renames),
        collisions=final_id_collisions(stored, moves),
    )


def find_moves(stored: Sequence[StoredJurisdiction], assignments: Mapping[str, Assignment]) -> List[Move]:
    id_counts = Counter(j.id for j in stored)
    moves = []
    for jurisdiction in stored:
        if jurisdiction.geoid is None or jurisdiction.geoid not in assignments:
            continue
        new_id = to_jurisdiction_ocdid(assignments[jurisdiction.geoid].division_ocdid)
        if new_id == jurisdiction.id:
            continue
        moves.append(Move(
            geoid=jurisdiction.geoid,
            level=jurisdiction.level,
            old_id=jurisdiction.id,
            new_id=new_id,
            ambiguous=id_counts[jurisdiction.id] > 1,
        ))
    return moves


def rewrites_longest_first(moves: Sequence[Move]) -> Tuple[Rewrite, ...]:
    # Longest first, so a local ID under a moved county matches its own rewrite before the county's
    rewrites = []
    for move in moves:
        rewrites.extend(rewrites_for(move.old_id, move.new_id))
    return tuple(sorted(rewrites, key=lambda rewrite: len(rewrite[0]), reverse=True))


def renames_for(move: Move) -> List[Rename]:
    officials_file = Rename(
        source=PROJECT_ROOT / jurisdiction_to_file(move.old_id),
        target=PROJECT_ROOT / jurisdiction_to_file(move.new_id),
    )
    pipeline_folder = Rename(
        source=PROJECT_ROOT / "data_source" / jurisdiction_ocdid_to_folder(move.old_id),
        target=PROJECT_ROOT / "data_source" / jurisdiction_ocdid_to_folder(move.new_id),
    )
    return [officials_file, pipeline_folder]


def final_id_collisions(stored: Sequence[StoredJurisdiction], moves: Sequence[Move]) -> Tuple[str, ...]:
    new_id_by_geoid = {move.geoid: move.new_id for move in moves}
    final_ids = []
    for jurisdiction in stored:
        if jurisdiction.level == Level.STATE:
            continue
        final_ids.append(new_id_by_geoid.get(jurisdiction.geoid or "", jurisdiction.id))
    counts = Counter(final_ids)
    return tuple(sorted(ocdid for ocdid, count in counts.items() if count > 1))


def rewrite_tree(node: Any, rewrites: Sequence[Rewrite]) -> Any:
    """A copy of a loaded YAML/JSON tree with every OCD-ID string rewritten."""
    if isinstance(node, str):
        return rewrite_ocdid(node, rewrites)
    if isinstance(node, dict):
        return {key: rewrite_tree(value, rewrites) for key, value in node.items()}
    if isinstance(node, list):
        return [rewrite_tree(value, rewrites) for value in node]
    return node


def entry_changes(plan: MigrationPlan, geoid: Optional[str], parent_ocdids: Optional[Sequence[str]]) -> Dict[str, Any]:
    """Fields to update on one jurisdictions.yml entry; empty if nothing changes."""
    changes: Dict[str, Any] = {}
    new_id_by_geoid = plan.new_id_by_geoid
    if geoid in new_id_by_geoid:
        changes["id"] = new_id_by_geoid[geoid]
    if parent_ocdids:
        new_parents = [rewrite_ocdid(parent, plan.rewrites) for parent in parent_ocdids]
        if new_parents != list(parent_ocdids):
            changes["parent_ocdids"] = new_parents
    return changes
