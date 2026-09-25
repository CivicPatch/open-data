from scripts.ocdids.migrate_plan import entry_changes, plan_migration, rewrite_tree
from scripts.ocdids.models import Assignment, Source
from scripts.ocdids.stored import Level, StoredJurisdiction

OLD = "ocd-jurisdiction/country:us/state:ma/county:middlesex/place:concord/government"
NEW = "ocd-jurisdiction/country:us/state:ma/place:concord/government"
NEW_DIVISION = "ocd-division/country:us/state:ma/place:concord"


def stored(geoid, ocdid, name="Concord town", level=Level.LOCAL):
    return StoredJurisdiction(level=level, id=ocdid, name=name, geoid=geoid)


def registry_assignment(geoid, division_ocdid):
    return Assignment(geoid=geoid, division_ocdid=division_ocdid, minted_ocdid=division_ocdid, source=Source.REGISTRY)


def concord_plan(extra_stored=()):
    entries = [stored("2501715060", OLD), *extra_stored]
    return plan_migration("ma", entries, {"2501715060": registry_assignment("2501715060", NEW_DIVISION)})


class TestPlanMigration:
    def test_moves_changed_id(self):
        plan = concord_plan()
        assert [(m.old_id, m.new_id) for m in plan.moves] == [(OLD, NEW)]

    def test_renames_officials_file_and_folder(self):
        names = [(r.source.name, r.target.name) for r in concord_plan().renames]
        assert names == [
            ("county_middlesex__place_concord.yml", "place_concord.yml"),
            ("county_middlesex__place_concord", "place_concord"),
        ]

    def test_shared_old_id_is_ambiguous_and_not_renamed(self):
        plan = concord_plan(extra_stored=[stored("2599999", OLD, name="Other town")])
        assert plan.moves[0].ambiguous
        assert plan.renames == ()

    def test_collision_with_unmoved_entry(self):
        plan = concord_plan(extra_stored=[stored("2599999", NEW, name="Other town")])
        assert plan.collisions == (NEW,)

    def test_unchanged_id_is_not_moved(self):
        plan = plan_migration("ma", [stored("1", NEW)], {"1": registry_assignment("1", NEW_DIVISION)})
        assert plan.moves == ()


class TestRewriteTree:
    def test_rewrites_jurisdiction_division_and_children(self):
        tree = {"roles": [{
            "jurisdiction_ocdid": OLD,
            "division_ocdid": "ocd-division/country:us/state:ma/county:middlesex/place:concord/precinct:2",
            "note": "unrelated",
        }]}
        assert rewrite_tree(tree, concord_plan().rewrites) == {"roles": [{
            "jurisdiction_ocdid": NEW,
            "division_ocdid": "ocd-division/country:us/state:ma/place:concord/precinct:2",
            "note": "unrelated",
        }]}

    def test_does_not_match_a_longer_name(self):
        concordia = "ocd-division/country:us/state:ma/county:middlesex/place:concordia"
        assert rewrite_tree(concordia, concord_plan().rewrites) == concordia

    def test_input_is_not_modified(self):
        tree = {"id": OLD}
        rewrite_tree(tree, concord_plan().rewrites)
        assert tree == {"id": OLD}


class TestEntryChanges:
    def test_new_id(self):
        assert entry_changes(concord_plan(), "2501715060", None) == {"id": NEW}

    def test_nothing_for_unmoved_entry(self):
        assert entry_changes(concord_plan(), "2599999", ["ocd-jurisdiction/country:us/state:ma/government"]) == {}
