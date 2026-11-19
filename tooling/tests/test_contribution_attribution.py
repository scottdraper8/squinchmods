import importlib.util
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

LOADER = SourceFileLoader(
    "contribution_policy",
    str(Path(__file__).parents[1] / "check-contribution-attribution"),
)
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
POLICY = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(POLICY)


class ContributionAttributionTests(unittest.TestCase):
    def test_neutral_metadata_passes(self) -> None:
        self.assertEqual(
            POLICY.metadata_violations("commit", "Fix runtime startup"), []
        )
        self.assertEqual(
            POLICY.branch_violations("branch", "search-probes/runtime-startup"), []
        )

    def test_named_assistant_fails_in_branch_and_text(self) -> None:
        self.assertTrue(POLICY.branch_violations("branch", "codex/runtime-startup"))
        self.assertTrue(
            POLICY.metadata_violations("pull request", "Implemented with Claude")
        )

    def test_unnamed_attribution_fails(self) -> None:
        self.assertTrue(
            POLICY.metadata_violations("commit", "AI-assisted implementation")
        )
        self.assertTrue(
            POLICY.metadata_violations("commit", "Generated-by: coding assistant")
        )

    def test_technical_agent_language_and_dependabot_pass(self) -> None:
        self.assertEqual(
            POLICY.metadata_violations("commit", "Add agent-control endpoint"), []
        )
        self.assertEqual(
            POLICY.metadata_violations(
                "commit", "Bump example from 1 to 2\n\nCo-authored-by: dependabot[bot]"
            ),
            [],
        )

    def test_github_pull_request_event_checks_branch_body_and_commits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            POLICY.subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            POLICY.subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=root,
                check=True,
            )
            POLICY.subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=root, check=True
            )
            (root / "file").write_text("base", encoding="utf-8")
            POLICY.subprocess.run(["git", "add", "file"], cwd=root, check=True)
            POLICY.subprocess.run(
                ["git", "commit", "-qm", "Base"], cwd=root, check=True
            )
            base = POLICY.git("rev-parse", "HEAD", cwd=root).strip()
            (root / "file").write_text("head", encoding="utf-8")
            POLICY.subprocess.run(
                ["git", "commit", "-qam", "Neutral change"], cwd=root, check=True
            )
            head = POLICY.git("rev-parse", "HEAD", cwd=root).strip()
            event = root / "event.json"
            event.write_text(
                POLICY.json.dumps(
                    {
                        "pull_request": {
                            "title": "Runtime change",
                            "body": "Generated with ChatGPT",
                            "base": {"sha": base},
                            "head": {"sha": head, "ref": "feature/runtime-change"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(POLICY.check_event(root, event))


if __name__ == "__main__":
    unittest.main()
