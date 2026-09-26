from squinch_minecraft_third_party.catalog import CatalogArtifact
from squinch_minecraft_third_party import modrinth


def artifact(artifact_id: str, version_id: str, version_number: str) -> CatalogArtifact:
    return CatalogArtifact(
        id=artifact_id,
        project_slug="example",
        project_id="project",
        minecraft_version="1.21.1",
        loader="fabric",
        version_number=version_number,
        version_id=version_id,
        filename=f"{artifact_id}.jar",
        sha256="0" * 64,
        status="diagnostic-only",
        reason="test",
        required_dependencies=(),
        source_id="source",
    )


def test_audit_latest_catalog_marks_current_and_control_pins(monkeypatch) -> None:
    monkeypatch.setattr(
        modrinth,
        "_versions",
        lambda *_args, **_kwargs: [{
            "id": "latest-id",
            "version_number": "2.0",
            "version_type": "release",
            "date_published": "2026-01-01T00:00:00Z",
        }],
    )

    result = modrinth.audit_latest_catalog([
        artifact("latest", "latest-id", "2.0"),
        artifact("control", "old-id", "1.0"),
    ])

    pins = {value["artifact_id"]: value for value in result["groups"][0]["pins"]}
    assert pins["latest"]["is_latest"] is True
    assert pins["control"]["is_latest"] is False
    assert result["groups"][0]["channel_policy"] == "release"
