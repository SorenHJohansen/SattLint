# ruff: noqa: F403, F405
from ._docgen_fixture_builders import *
from ._docgen_test_support import *


def test_classify_documentation_structure_detects_recursive_categories():
    base_picture = _build_documentation_fixture()

    classification = classify_documentation_structure(
        base_picture,
        config_module.get_documentation_config(),
    )

    operations = {entry.name for entry in classification.categories["ops"]}
    equipment_modules = {entry.name for entry in classification.categories["em"]}
    recipe_parameters = {entry.name for entry in classification.categories["rp"]}
    engineering_parameters = {entry.name for entry in classification.categories["ep"]}
    user_parameters = {entry.name for entry in classification.categories["up"]}

    assert operations == {"Prepare"}
    assert equipment_modules == {"Tank", "DiluteTank"}
    assert "RecipeSP" in recipe_parameters
    assert "EngineeringLimit" in engineering_parameters
    assert "GlobalLimit" in engineering_parameters
    assert "UserTarget" in user_parameters

    operation_entry = classification.categories["ops"][0]
    assert {entry.name for entry in classification.descendants(operation_entry, category="rp")} == {"RecipeSP"}


def test_generate_docx_renders_fs_style_sections(tmp_path):
    base_picture = _build_documentation_fixture()
    out_path = tmp_path / "functional-spec.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    assert out_path.exists()

    document = Document(out_path)
    paragraph_text = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    assert "Introduction" in paragraph_text
    assert "S88 Physical model" in paragraph_text
    assert "S88 Procedural model" in paragraph_text
    assert "Measurements and logging" in paragraph_text
    assert "Communication" in paragraph_text
    assert "Equipment Module Tank" in paragraph_text
    assert "Operation Prepare" in paragraph_text
    assert "Change Log" in paragraph_text


def test_classify_documentation_scope_by_moduletype_name():
    base_picture = _build_documentation_fixture()
    documentation_cfg = config_module.get_documentation_config()
    documentation_cfg["units"] = {
        "mode": "moduletype_names",
        "instance_paths": [],
        "moduletype_names": ["ApplTank"],
    }

    classification = classify_documentation_structure(base_picture, documentation_cfg)

    assert classification.scope is not None
    assert [entry.name for entry in classification.scope.roots or []] == ["UnitA"]
    assert {entry.name for entry in classification.categories["ops"]} == {"Prepare"}
    assert {entry.name for entry in classification.categories["em"]} == {"Tank"}


def test_discover_documentation_unit_candidates_returns_unit_roots():
    base_picture = _build_documentation_fixture()
    classification = classify_documentation_structure(
        base_picture,
        config_module.get_documentation_config(),
    )

    candidates = discover_documentation_unit_candidates(classification)

    assert {entry.name for entry in candidates} == {"UnitA", "DilutionTrain"}


def test_wrapper_heavy_classification_anchors_real_sections():
    base_picture = _build_wrapper_documentation_fixture()

    classification = classify_documentation_structure(
        base_picture,
        config_module.get_documentation_config(),
    )

    assert {entry.name for entry in classification.categories["em"]} == {"EM_FILL"}
    assert {entry.name for entry in classification.categories["ops"]} == {"Prepare"}

    candidates = discover_documentation_unit_candidates(classification)
    assert {entry.name for entry in candidates} == {"UnitA"}


def test_generate_docx_renders_wrapper_heavy_fs_sections(tmp_path):
    base_picture = _build_wrapper_documentation_fixture()
    out_path = tmp_path / "functional-spec-wrapper.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    document = Document(out_path)
    paragraph_text = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    assert "Process Cell - UF/DF" in paragraph_text
    assert "Unit Class definition: UF/DF Tank" in paragraph_text
    assert "Measurements and logging" in paragraph_text
    assert "Communication" in paragraph_text
    assert "Equipment Module Fill" in paragraph_text
    assert "Operation Prepare" in paragraph_text
    assert "Change Log" in paragraph_text


def test_generate_docx_respects_single_unit_scope(tmp_path):
    base_picture = _build_documentation_fixture()
    out_path = tmp_path / "functional-spec-scoped.docx"
    documentation_cfg = config_module.get_documentation_config()
    documentation_cfg["units"] = {
        "mode": "moduletype_names",
        "instance_paths": [],
        "moduletype_names": ["ApplTank"],
    }

    generate_docx(
        base_picture,
        out_path,
        documentation_config=documentation_cfg,
    )

    document = Document(out_path)
    paragraph_text = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    assert "Operation Prepare" in paragraph_text
    assert "Equipment Module Tank" in paragraph_text
    assert "DilutionTrain" not in paragraph_text
    assert "Equipment Module DiluteTank" not in paragraph_text


def test_generate_docx_uses_template_shaped_front_matter_and_tables(tmp_path):
    base_picture = _build_wrapper_documentation_fixture()
    out_path = tmp_path / "functional-spec-template-shaped.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    document = Document(out_path)
    headers = _table_headers(document)

    assert ["NNE Author", "NNE Author", "NNE Author"] in headers
    assert ["", "Document", "NN Doc. no."] in headers
    assert ["Unit", "Unit Class", "Danish Description", "Unit Definition"] in headers
    assert [
        "Measurement",
        "Tag",
        "Min",
        "Max",
        "Eng. Unit",
        "Log interval\n(Max)",
        "Dead-band\nrelative",
        "Log interval \n(Min)",
    ] in headers
    assert ["From", "Comment"] in headers


def test_generate_docx_renders_upgrade_insights_for_version_drift(tmp_path):
    base_picture = _build_version_drift_doc_fixture()
    out_path = tmp_path / "functional-spec-upgrades.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    document = Document(out_path)
    paragraph_text = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    assert "Upgrade insights" in paragraph_text
    assert "Module Mixer" in paragraph_text
    assert any("Equation 'Logic' changed" in paragraph for paragraph in paragraph_text)


def test_generate_docx_renders_sfc_sequences_as_tables(tmp_path):
    base_picture = _build_sequence_doc_fixture()
    out_path = tmp_path / "functional-spec-sfc.docx"

    generate_docx(
        base_picture,
        out_path,
        documentation_config=config_module.get_documentation_config(),
    )

    document = Document(out_path)
    headers = _table_headers(document)
    table_text = _table_text(document)

    assert ["Type", "Name", "Condition / Detail", "Enter", "Active", "Exit"] in headers
    assert "Sub sequence - MainSequence" in [
        paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()
    ]
    assert "Init step" in table_text
    assert "Init" in table_text
    assert "p.GotoRunDone = True" in table_text
    assert "Transition" in table_text
    assert "Tr1" in table_text
    assert "p.GotoRun OR \np.Run" in table_text
    assert "Step" in table_text
    assert "Tarering" in table_text
    assert "CopyString(StepText.Tarering, Step, si)" in table_text
    assert "NOT(Dv.Tara_execute) AND \nNOT(ProfibusError)" in table_text
    assert not any("SFCStep(" in text for text in table_text)
    assert not any("SFCTransition(" in text for text in table_text)


def test_classify_documentation_scope_by_instance_path_deduplicates_and_tracks_unmatched_values():
    base_picture = _build_documentation_fixture()
    documentation_cfg = config_module.get_documentation_config()
    documentation_cfg["units"] = {
        "mode": "instance_paths",
        "instance_paths": ["BasePicture.UnitA", "UnitA", "Missing.Unit"],
        "moduletype_names": [],
    }

    classification = classify_documentation_structure(base_picture, documentation_cfg)

    assert classification.scope is not None
    assert classification.scope.mode == "instance_paths"
    assert classification.scope.requested_values == ["BasePicture.UnitA", "UnitA", "Missing.Unit"]
    assert [entry.name for entry in classification.scope.roots or []] == ["UnitA"]
    assert classification.scope.unmatched_values == ["Missing.Unit"]
    assert {entry.name for entry in classification.categories["ops"]} == {"Prepare"}
    assert {entry.name for entry in classification.categories["em"]} == {"Tank"}
    assert {entry.name for entry in classification.uncategorized} == {"MESInfo", "Coordinate"}


def test_classify_documentation_scope_falls_back_to_all_for_invalid_units_settings():
    base_picture = _build_documentation_fixture()

    invalid_shape = classify_documentation_structure(base_picture, {"units": "bad"})
    unknown_mode = classify_documentation_structure(base_picture, {"units": {"mode": "mystery"}})

    assert invalid_shape.scope is not None
    assert invalid_shape.scope.mode == "all"
    assert invalid_shape.scope.roots == []
    assert invalid_shape.scope.unmatched_values is None
    assert unknown_mode.scope is not None
    assert unknown_mode.scope.mode == "all"
    assert unknown_mode.scope.roots == []


def test_sequence_render_rows_cover_branching_nested_and_fallback_nodes():
    sequence = Sequence(
        name="ComplexSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCAlternative(
                branches=[
                    [SFCStep(kind="init", name="AltInit", code=SFCCodeBlocks())],
                    [SFCBreak()],
                ]
            ),
            SFCParallel(
                branches=[
                    [SFCTransition(name="ParallelGate", condition=True)],
                    [SFCFork(targets=("ParallelDone",))],
                ]
            ),
            SFCSubsequence(
                name="NestedSequence",
                body=[SFCStep(kind="step", name="NestedStep", code=SFCCodeBlocks())],
            ),
            SFCTransitionSub(
                name="TransitionBranch",
                body=[SFCTransition(name="NestedTransition", condition=False)],
            ),
            SFCFork(targets=("Elsewhere",)),
            SFCBreak(),
            (const.KEY_ASSIGN, {"var_name": "Output"}, True),
        ],
    )

    rows = _sequence_render_rows(sequence)

    assert [row.node_type for row in rows] == [
        "Alternative",
        "Branch",
        "Init step",
        "Branch",
        "Break",
        "Parallel",
        "Branch",
        "Transition",
        "Branch",
        "Fork",
        "Subsequence",
        "Step",
        "Transition section",
        "Transition",
        "Fork",
        "Break",
        "Statement",
    ]
    assert rows[2].detail == "Alternative branch 1: Initial step"
    assert rows[7].detail == "Parallel branch 1: True"
    assert rows[11].detail == "Subsequence NestedSequence: Execution step"
    assert rows[13].detail == "Transition section TransitionBranch: False"
    assert rows[14].detail == "Fork target"
    assert rows[15].detail == "Break sequence flow"
    assert rows[16].detail == "Output = True"
