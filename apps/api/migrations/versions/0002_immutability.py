"""Enforce immutable version payloads and project/kind version references."""

from alembic import op

revision = "0002_immutability"
down_revision = "8a8aa6e5a160"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      CREATE FUNCTION evaldock_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'Versioned records are immutable; create a new version'; END; $$;
      CREATE TRIGGER immutable_versions BEFORE UPDATE OR DELETE ON versions FOR EACH ROW EXECUTE FUNCTION evaldock_immutable();
      CREATE TRIGGER immutable_cases BEFORE UPDATE OR DELETE ON test_cases FOR EACH ROW EXECUTE FUNCTION evaldock_immutable();
      CREATE FUNCTION evaldock_resource_identity() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN IF NEW.kind <> OLD.kind OR NEW.project_id <> OLD.project_id THEN
        RAISE EXCEPTION 'Resource kind and project are immutable'; END IF; RETURN NEW; END; $$;
      CREATE TRIGGER resource_identity BEFORE UPDATE ON resources FOR EACH ROW EXECUTE FUNCTION evaldock_resource_identity();
      CREATE FUNCTION evaldock_experiment_versions() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NOT EXISTS(SELECT 1 FROM versions v JOIN resources r ON r.id=v.resource_id WHERE v.id=NEW.dataset_version_id AND r.kind='dataset' AND r.project_id=NEW.project_id)
        OR NOT EXISTS(SELECT 1 FROM versions v JOIN resources r ON r.id=v.resource_id WHERE v.id=NEW.suite_version_id AND r.kind='suite' AND r.project_id=NEW.project_id)
        OR (NEW.target_version_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM versions v JOIN resources r ON r.id=v.resource_id WHERE v.id=NEW.target_version_id AND r.kind='target' AND r.project_id=NEW.project_id))
        OR (NEW.baseline_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM experiments e WHERE e.id=NEW.baseline_id AND e.project_id=NEW.project_id))
        OR (NEW.parent_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM experiments e WHERE e.id=NEW.parent_id AND e.project_id=NEW.project_id)) THEN
          RAISE EXCEPTION 'Experiment references incompatible project/version kinds';
        END IF;
        IF TG_OP = 'UPDATE' AND (NEW.dataset_version_id <> OLD.dataset_version_id OR NEW.suite_version_id <> OLD.suite_version_id OR NEW.target_version_id IS DISTINCT FROM OLD.target_version_id OR NEW.baseline_id IS DISTINCT FROM OLD.baseline_id OR NEW.project_id <> OLD.project_id) THEN
          RAISE EXCEPTION 'Experiment version references are immutable';
        END IF;
        RETURN NEW;
      END; $$;
      CREATE TRIGGER experiment_versions BEFORE INSERT OR UPDATE ON experiments FOR EACH ROW EXECUTE FUNCTION evaldock_experiment_versions();
    """)


def downgrade():
    op.execute(
        "DROP TRIGGER experiment_versions ON experiments; DROP FUNCTION evaldock_experiment_versions(); DROP TRIGGER resource_identity ON resources; DROP FUNCTION evaldock_resource_identity(); DROP TRIGGER immutable_cases ON test_cases; DROP TRIGGER immutable_versions ON versions; DROP FUNCTION evaldock_immutable();"
    )
