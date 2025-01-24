"""Documentation integrity: machine-checkable parts of the deliverables checklist.

These tests do not judge prose quality. They check the things that must never drift:
exact required strings, minimum lengths, that every generated table is current and present
in all five placements, that links resolve, that named people appear only where allowed,
that the documents stay on this repository's topic, and that nothing large or sensitive sits
in the repository.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from experiments.sync_docs import sync

PROPOSED_ENDEAVOR = (
    "Design and implement advanced machine learning and large language model architectures "
    "for secure, reliable system-level optimization in order to enhance the efficiency, "
    "reliability, and security of U.S. digital infrastructure and accelerate the deployment of "
    "next-generation artificial intelligence (AI) applications."
)
STATUS_BANNER = (
    "Draft reference implementation — values printed in the source paper are shown for "
    "reference only; see RESULTS.md for the values this code produces and the conditions under "
    "which it produces them."
)

# Profiles that may appear in chapter 12 of the project report of this repository.
RESEARCHERS_HERE = ("Zhiling Lan",)
# Names that must not appear anywhere in this repository.
RESEARCHERS_ELSEWHERE = (
    "Minxuan Zhou",
    "Binghui Wang",
    "Nathaniel Hudson",
    "Weizhao Jin",
    "Shuli Jiang",
)
INVESTIGATION = "docs/investigations/01-ddqn-scheduling-reproduction.md"
DIAGRAMS = (
    "01-system-overview.md",
    "02-scheduler-detail.md",
    "03-experiment-flow.md",
    "04-deployment-sketch.md",
)
NOTEBOOKS = ("01_scheduler_reproduction.ipynb", "02_scheduler_ablation.ipynb")
CHARTS = ("scheduling.png",)
# The LLM-style workload study: a synthetic task mix, never a language model.
LLM_CHART = "scheduling_llm.png"
LLM_RUN = "experiments/results/reference/scheduler_llm"
LLM_SCOPE_SENTENCE = "no language model is run"
# The one variant run on that profile was defined after its results had been seen.
LLM_ABLATION = "starvation_bounded_slice"
LLM_ABLATION_STALE = re.compile(
    r"(?i)no ablation (?:was|were|has been) run on (?:this|the|that) profile"
    r"|no ablation (?:was|were|has been) run on it\b"
    r"|bounded forced (?:time )?slice[^.]{0,80}\b(?:it )?has not been run\b"
    r"|not isolated by (?:an|any) experiment"
)
LLM_OVERCLAIM = re.compile(
    r"(?i)\bLLM (?:benchmark|serving experiment|scheduling results)\b|served by an LLM"
    r"|real (?:LLM|inference) (?:requests|traffic|traces?) (?:were|was)"
    r"|(?:ran|run|runs|running|served|benchmarked) (?:a|an|the) (?:large )?language model\b"
)
# Method-level vocabulary of the companion project; a short pointer to the companion by name
# is fine, describing its method here is not.
OFF_TOPIC = re.compile(r"\bFedAvg\b|\bOpacus\b|\bFEMNIST\b|UCI Adult|\bworkclass\b|\bFlower\b")

README = "README.md"
RESULTS = "experiments/results/RESULTS.md"
REPORT = "docs/report/PROJECT_REPORT.md"
POSTER = "docs/poster/POSTER.md"
SLIDES = "docs/slides/PRESENTATION.md"
DATA_CARDS = "data/README.md"
FIVE_PLACEMENTS = (RESULTS, README, REPORT, POSTER, SLIDES)
# Leftovers of the combined project this repository was split from.
SPLIT_LEFTOVERS = re.compile(
    r"SPLIT-TODO|track1_|track2_|\bTrack [12]\b|secure-systems-optimization"
    r"|Secure Systems Optimization|[Tt]wo source papers|[Bb]oth tracks"
)
# The documents talk about the problem, the implementation, the Before / After results and the
# limits. They do not discuss what the source paper states, leaves open or prints differently.
PAPER_DISCUSSION = re.compile(
    r"\b(?:notes?|open points?|gaps?) [AB]-F?[0-9]|\b[AB]-F[0-9]\b|[Cc]onstant predictor"
    r"|leaves? open|does not specify|not specified|as printed in Paper|\bPaper [AB]\b"
    r"|confirm or dispute"
)
IGNORED_DIRS = {
    ".venv", ".git", "__pycache__", ".pytest_cache", ".ruff_cache", "runs", "_executed",
    "adult", "cache", "femnist", "node_modules",
}  # fmt: skip

GENERATED = re.compile(
    r"<!-- BEGIN GENERATED: [\w\-]+ -->.*?<!-- END GENERATED: [\w\-]+ -->", re.DOTALL
)
FENCED = re.compile(r"```.*?```", re.DOTALL)
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _read(repo_root: Path, relative: str) -> str:
    path = repo_root / relative
    assert path.is_file(), f"missing required document: {relative}"
    return path.read_text(encoding="utf-8")


def _prose_words(text: str) -> int:
    """Words of hand-written prose: generated blocks and code blocks do not count."""
    return len(FENCED.sub(" ", GENERATED.sub(" ", text)).split())


def _flat(text: str) -> str:
    """Collapse whitespace and blockquote markers so wrapped quotations compare equal."""
    return re.sub(r"\s+", " ", re.sub(r"(?m)^\s*>\s?", "", text))


def _repo_files(repo_root: Path) -> list[Path]:
    files = []
    for path in repo_root.rglob("*"):
        relative = path.relative_to(repo_root)
        if any(part in IGNORED_DIRS or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.is_file():
            files.append(path)
    return files


def _documents(repo_root: Path) -> list[Path]:
    """Hand-written documents: Markdown, notebooks, citation and community files."""
    return [
        path
        for path in _repo_files(repo_root)
        if path.suffix in {".md", ".ipynb", ".cff", ".yml"} and "generated" not in path.parts
    ]


@pytest.mark.parametrize(
    ("relative", "minimum"), [(README, 3000), (REPORT, 8000), (INVESTIGATION, 2500)]
)
def test_long_documents_meet_their_minimum_length(
    repo_root: Path, relative: str, minimum: int
) -> None:
    words = _prose_words(_read(repo_root, relative))
    assert words >= minimum, f"{relative}: {words} words of prose, need at least {minimum}"


def test_required_documents_exist(repo_root: Path) -> None:
    required = [README, RESULTS, REPORT, POSTER, SLIDES, DATA_CARDS, INVESTIGATION,
                "LICENSE", "CITATION.cff", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md",
                "docs/DELIVERABLES_CHECKLIST.md", "docs/report/SOURCE_PAPER_FACTS.md",
                "docs/architecture/README.md", ".github/workflows/ci.yml",
                "configs/scheduler_llm_workload.yaml"]  # fmt: skip
    required += [f"docs/architecture/{name}" for name in DIAGRAMS]
    required += [f"notebooks/{name}" for name in NOTEBOOKS]
    required += [f".github/ISSUE_TEMPLATE/{name}.yml" for name in
                 ("bug_report", "replication_report", "benchmark_submission", "research_proposal")]  # fmt: skip
    missing = [name for name in required if not (repo_root / name).is_file()]
    assert not missing, f"missing deliverables: {missing}"


def test_public_metadata_has_no_template_placeholders(repo_root: Path) -> None:
    for relative in (
        README,
        "CITATION.cff",
        ".github/ISSUE_TEMPLATE/config.yml",
        POSTER,
        SLIDES,
    ):
        text = _read(repo_root, relative)
        assert "<owner>" not in text, f"{relative}: replace the owner placeholder"
        assert "to be added by the project owner" not in text, f"{relative}: add confirmed authors"
    readme = _read(repo_root, README)
    assert "https://github.com/fguo10-tech/ddqn-os-scheduling" in readme
    assert "Badges (placeholder)" not in readme


def test_status_banner_is_verbatim_in_readme(repo_root: Path) -> None:
    assert STATUS_BANNER in _flat(_read(repo_root, README))


@pytest.mark.parametrize("relative", [README, REPORT, SLIDES])
def test_proposed_endeavor_is_quoted_verbatim(repo_root: Path, relative: str) -> None:
    assert PROPOSED_ENDEAVOR in _flat(_read(repo_root, relative)), f"{relative}: quotation altered"


def test_proposed_endeavor_is_never_paraphrased(repo_root: Path) -> None:
    opening = "Design and implement advanced machine learning"
    for path in _repo_files(repo_root):
        if path.suffix != ".md":
            continue
        flat = _flat(path.read_text(encoding="utf-8"))
        assert flat.count(opening) == flat.count(
            PROPOSED_ENDEAVOR
        ), f"{path.relative_to(repo_root)}: the Proposed Endeavor sentence appears in altered form"


def test_generated_blocks_are_current(repo_root: Path) -> None:
    assert sync(check=True, root=repo_root) == 0, "run `make results` and commit the result"


@pytest.mark.parametrize("relative", FIVE_PLACEMENTS)
def test_comparison_tables_and_charts_are_in_all_five_placements(
    repo_root: Path, relative: str
) -> None:
    text = _read(repo_root, relative)
    assert re.search(
        r"BEGIN GENERATED: before_after_", text
    ), f"{relative}: no Before / After table"
    for chart in CHARTS:
        assert chart in text, f"{relative}: chart {chart} is not referenced"
    assert "always means better after" in _flat(text), f"{relative}: sign convention not stated"
    assert "| Improvement % |" in text and "| Delta (absolute) |" in text


@pytest.mark.parametrize("relative", FIVE_PLACEMENTS)
def test_llm_workload_study_is_in_all_five_placements(repo_root: Path, relative: str) -> None:
    text = _read(repo_root, relative)
    assert re.search(
        r"BEGIN GENERATED: llm_before_after_", text
    ), f"{relative}: no Before / After table of the LLM-style workload study"
    assert LLM_CHART in text, f"{relative}: chart {LLM_CHART} is not referenced"


@pytest.mark.parametrize("relative", [*FIVE_PLACEMENTS, DATA_CARDS])
def test_documents_say_that_no_language_model_is_run(repo_root: Path, relative: str) -> None:
    """The statement must be in hand-written prose, not only inside a generated table."""
    prose = _flat(GENERATED.sub(" ", _read(repo_root, relative))).lower()
    assert LLM_SCOPE_SENTENCE in prose, f"{relative}: must say that {LLM_SCOPE_SENTENCE}"


def test_no_document_claims_that_a_language_model_was_run(repo_root: Path) -> None:
    problems = []
    for path in _documents(repo_root):
        prose = GENERATED.sub(" ", path.read_text(encoding="utf-8"))
        found = sorted(set(LLM_OVERCLAIM.findall(prose)))
        if found:
            problems.append(f"{path.relative_to(repo_root)}: {found}")
    assert not problems, "\n".join(problems)


def test_reference_run_of_the_llm_workload_profile_is_complete(repo_root: Path) -> None:
    """Every [Reproduced] number of the study has its raw files, config and metadata."""
    import json

    run = repo_root / LLM_RUN
    for name in ("raw_episodes.csv", "summary.csv", "class_episodes.csv", "class_summary.csv",
                 "training_log.csv", "config_used.yaml", "metadata.json"):  # fmt: skip
        assert (run / name).is_file(), f"{LLM_RUN}/{name} is missing"
    meta = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    assert meta["seeds"] == [0, 1, 2, 3, 4], "the reference run uses the reporting seeds"
    assert "configs/scheduler_llm_workload.yaml" in meta["command"]
    assert meta["extra"]["class_metrics"] is True and meta["extra"]["smoke"] is False
    assert all(not seed["diverged"] for seed in meta["extra"]["per_seed"])
    used = (run / "config_used.yaml").read_text(encoding="utf-8")
    assert "inference_request:" in used and "finetune_job:" in used
    assert "cpu_bound:" not in used, "the profile replaces the classes of the benchmark config"
    for name in ("scheduling_llm.csv", "scheduling_llm.png", "scheduling_llm_by_class.csv",
                 "scheduling_llm_by_class.png"):  # fmt: skip
        assert (repo_root / "experiments/results/reference/before_after" / name).is_file(), name


def test_post_hoc_variant_of_the_llm_workload_study_is_complete_and_differs_in_one_setting(
    repo_root: Path,
) -> None:
    import json

    import yaml

    run = repo_root / LLM_RUN
    variant = run / "ablations" / LLM_ABLATION
    for name in ("raw_episodes.csv", "summary.csv", "class_episodes.csv", "class_summary.csv",
                 "training_log.csv", "config_used.yaml", "metadata.json"):  # fmt: skip
        assert (variant / name).is_file(), f"{LLM_RUN}/ablations/{LLM_ABLATION}/{name} is missing"
    meta = json.loads((variant / "metadata.json").read_text(encoding="utf-8"))
    assert meta["seeds"] == [0, 1, 2, 3, 4] and meta["extra"]["ablation"] == LLM_ABLATION
    assert meta["extra"]["class_metrics"] is True and meta["extra"]["smoke"] is False
    assert all(not seed["diverged"] for seed in meta["extra"]["per_seed"])
    reference = yaml.safe_load((run / "config_used.yaml").read_text(encoding="utf-8"))
    changed = yaml.safe_load((variant / "config_used.yaml").read_text(encoding="utf-8"))
    assert LLM_ABLATION in reference["scheduler"]["ablations"], "re-create the reference run"
    assert reference["scheduler"]["guardrails"]["starvation"]["forced_time_slice_ms"] is None
    assert changed["scheduler"]["guardrails"]["starvation"]["forced_time_slice_ms"] == 20.0
    changed["scheduler"]["guardrails"]["starvation"]["forced_time_slice_ms"] = None
    assert changed["scheduler"] == reference["scheduler"], "the variant changes one setting"
    assert changed["baselines"] == reference["baselines"]
    assert (repo_root / "experiments/results/reference/before_after/scheduling_llm_ablation.csv").is_file()  # fmt: skip


def test_baselines_are_identical_in_the_variant_and_the_reference_run(repo_root: Path) -> None:
    """The variant changes a guardrail setting, which no baseline or reference method uses."""
    import csv

    def rows(path: Path) -> dict[tuple[str, str], dict[str, str]]:
        with path.open(encoding="utf-8", newline="") as handle:
            return {
                (row["method"], row["load_profile"]): row
                for row in csv.DictReader(handle)
                if not row["method"].startswith("ddqn")
            }

    run = repo_root / LLM_RUN
    reference = rows(run / "summary.csv")
    variant = rows(run / "ablations" / LLM_ABLATION / "summary.csv")
    assert reference and reference == variant


@pytest.mark.parametrize("relative", [RESULTS, REPORT, INVESTIGATION])
def test_post_hoc_variant_table_is_placed_and_labelled(repo_root: Path, relative: str) -> None:
    text = _read(repo_root, relative)
    assert "BEGIN GENERATED: llm_ablation" in text, f"{relative}: variant table is missing"
    block = re.search(
        r"BEGIN GENERATED: llm_ablation -->(.*?)<!-- END GENERATED: llm_ablation", text, re.S
    )
    assert block is not None
    assert "Post hoc variant" in block.group(
        1
    ) and "By this rule the explanation is" in block.group(1)
    prose = _flat(GENERATED.sub(" ", text)).lower()
    assert "post hoc" in prose, f"{relative}: the variant must be called post hoc in the prose"
    assert "exploratory" in prose, f"{relative}: the variant must be called exploratory"


def test_every_mention_of_the_variant_says_it_is_post_hoc(repo_root: Path) -> None:
    """A document that names the bounded forced slice result must not present it as planned."""
    problems = []
    for path in _documents(repo_root):
        prose = _flat(GENERATED.sub(" ", path.read_text(encoding="utf-8")))
        if LLM_ABLATION_STALE.search(prose):
            problems.append(
                f"{path.relative_to(repo_root)}: says the variant was not run: "
                f"{LLM_ABLATION_STALE.search(prose).group(0)!r}"
            )
        mentions = re.search(r"(?i)bounded forced|bounds the forced|bounding the forced", prose)
        if mentions and "post hoc" not in prose.lower():
            problems.append(
                f"{path.relative_to(repo_root)}: mentions the variant without 'post hoc'"
            )
    assert not problems, "\n".join(problems)


def test_comparison_columns_are_exact(repo_root: Path) -> None:
    header = (
        "| Metric | Unit | Direction | Before Method | Before Value | After Method | After Value "
        "| Delta (absolute) | Improvement % | Source Label |"
    )
    for relative in (RESULTS, README, REPORT):
        assert header in _read(
            repo_root, relative
        ), f"{relative}: full Before / After header missing"


@pytest.mark.parametrize("relative", [README, DATA_CARDS, REPORT])
def test_documents_say_the_workloads_are_synthetic(repo_root: Path, relative: str) -> None:
    text = _flat(_read(repo_root, relative)).lower()
    assert "synthetic" in text, f"{relative}: must say that the workloads are synthetic"
    assert "no real" in text, f"{relative}: must say that there is no real dataset"


def test_documents_stay_on_this_repositorys_topic(repo_root: Path) -> None:
    """No leftover of the combined project, no method vocabulary of the companion project, and
    no discussion of what the source paper states or leaves open."""
    problems = []
    for path in _documents(repo_root):
        relative = path.relative_to(repo_root)
        text = path.read_text(encoding="utf-8")
        prose = GENERATED.sub(" ", text)
        for pattern, what in (
            (SPLIT_LEFTOVERS, "leftover"),
            (OFF_TOPIC, "companion vocabulary"),
            (PAPER_DISCUSSION, "discussion of the source paper"),
        ):
            found = sorted(set(pattern.findall(prose)))
            if found:
                problems.append(f"{relative}: {what}: {found}")
    assert not problems, "\n".join(problems)


def test_named_researchers_appear_only_in_the_collaboration_chapter(repo_root: Path) -> None:
    allowed = {repo_root / REPORT, repo_root / "docs/report/references.bib",
               repo_root / "tests/test_docs_integrity.py"}  # fmt: skip
    for path in _repo_files(repo_root):
        if path.suffix in {".png", ".pdf", ".pt", ".ipynb_checkpoints"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if path != repo_root / "tests/test_docs_integrity.py":
            elsewhere = [name for name in RESEARCHERS_ELSEWHERE if name in text]
            assert (
                not elsewhere
            ), f"{path.relative_to(repo_root)} names {elsewhere}; they belong to the companion"
        if path in allowed:
            continue
        found = [name for name in RESEARCHERS_HERE if name in text]
        assert (
            not found
        ), f"{path.relative_to(repo_root)} names {found}; only the report chapter may"
    report = _read(repo_root, REPORT)
    start = re.search(r"(?m)^## 12\b.*$", report)
    end = re.search(r"(?m)^## 13\b.*$", report)
    assert start and end, "report chapters 12 and 13 must exist"
    chapter = report[start.start() : end.start()]
    outside = report[: start.start()] + GENERATED.sub(" ", report[end.start() :])
    references_start = outside.rfind("References")
    body_outside = outside if references_start < 0 else outside[:references_start]
    for name in RESEARCHERS_HERE:
        assert name in chapter, f"profile of {name} missing from chapter 12"
        assert name not in body_outside, f"{name} is named outside chapter 12"
    flat = _flat(chapter).lower()
    for phrase in ("illustrative", "not a collaborator", "co-author", "endorser", "target / tbd"):
        assert phrase in flat, f"chapter 12 lacks the disclaimer wording {phrase!r}"
    assert not re.search(
        r"\b(he|she|his|her|him|hers)\b", _flat(chapter)
    ), "gendered pronoun in chapter 12"


def test_architecture_diagrams_each_have_one_mermaid_block(repo_root: Path) -> None:
    for name in DIAGRAMS:
        text = _read(repo_root, f"docs/architecture/{name}")
        blocks = re.findall(r"```mermaid\n(.*?)```", text, flags=re.DOTALL)
        assert len(blocks) == 1, f"{name}: expected exactly one mermaid block, found {len(blocks)}"
        body = blocks[0]
        assert re.match(
            r"\s*(flowchart|graph|sequenceDiagram|stateDiagram|classDiagram)", body
        ), name
        for opening, closing in ("[]", "()", "{}"):
            assert body.count(opening) == body.count(
                closing
            ), f"{name}: unbalanced {opening}{closing}"
        assert body.count('"') % 2 == 0, f"{name}: unbalanced quotes"
        for heading in ("Assumptions", "alternatives"):
            assert heading.lower() in text.lower(), f"{name}: section '{heading}' missing"


def test_relative_links_and_images_resolve(repo_root: Path) -> None:
    broken = []
    for path in _repo_files(repo_root):
        if path.suffix != ".md" or "generated" in path.parts:
            continue
        text = FENCED.sub(" ", path.read_text(encoding="utf-8"))
        for target in LINK.findall(text):
            if re.match(r"^(https?:|mailto:|#)", target) or "<owner>" in target:
                continue
            resolved = (path.parent / target.split("#")[0]).resolve()
            if not resolved.exists():
                broken.append(f"{path.relative_to(repo_root)} -> {target}")
    assert not broken, "broken relative links:\n" + "\n".join(broken)


def test_notebooks_are_clean_and_end_with_interpretation(repo_root: Path) -> None:
    nbformat = pytest.importorskip("nbformat")
    for name in NOTEBOOKS:
        notebook = nbformat.read(repo_root / "notebooks" / name, as_version=4)
        code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
        assert code_cells, f"{name} has no code"
        assert all(
            not cell.get("outputs") for cell in code_cells
        ), f"{name} is committed with outputs"
        last = notebook.cells[-1]
        assert last.cell_type == "markdown" and "Interpretation and limits" in last.source, name


def test_nothing_large_sensitive_or_secret_is_in_the_repository(repo_root: Path) -> None:
    secret = re.compile(
        r"AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{36}"
        r"|sk-[A-Za-z0-9]{32,}|xox[baprs]-[A-Za-z0-9-]{20,}"
    )
    local_path = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/")
    for path in _repo_files(repo_root):
        relative = path.relative_to(repo_root)
        size = path.stat().st_size
        # Result CSVs of the reference run are evidence and may be a few MB; datasets may not
        # be committed at all (see the file-name check below).
        assert (
            size <= 5_000_000
        ), f"{relative} is {size / 1e6:.1f} MB; large files must not be committed"
        assert path.name not in {
            "adult.data",
            "adult.test",
            ".env",
        }, f"{relative} must not be committed"
        if path.suffix in {".png", ".pdf", ".pt", ".npz", ".ico"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        assert not secret.search(text), f"{relative} looks like it contains a secret"
        assert not local_path.search(
            text
        ), f"{relative} contains a local absolute path or user name"
