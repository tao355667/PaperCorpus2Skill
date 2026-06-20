from papercorpus2skill.skill_state import ConceptThread, SkillState, SummaryChunk


def test_skill_state_merges_section_expressions_with_counts() -> None:
    state = SkillState(domain="web development education")

    state.apply_summary(
        SummaryChunk(
            domain="web development education",
            purpose="Help write papers.",
            section_expressions={"introduction": ["Prior work has increasingly emphasized resilient interfaces."]},
            concept_threads=[],
        )
    )
    state.apply_summary(
        SummaryChunk(
            domain="web development education",
            purpose="Help write papers.",
            section_expressions={"introduction": ["prior work has increasingly emphasized resilient interfaces"]},
            concept_threads=[],
        )
    )

    expression = state.section_expressions["introduction"][0]
    assert expression.text == "Prior work has increasingly emphasized resilient interfaces."
    assert expression.count == 2


def test_skill_state_merges_concept_threads_across_sections() -> None:
    state = SkillState(domain="remote photoplethysmography")

    state.apply_summary(
        SummaryChunk(
            domain="remote photoplethysmography",
            purpose="Help write papers.",
            section_expressions={},
            concept_threads=[
                ConceptThread(
                    concept="motion artifact suppression",
                    aliases=["motion artifacts"],
                    section_roles={
                        "introduction": ["Frames motion artifacts as a key robustness challenge."],
                        "method": ["Links suppression to temporal filtering modules."],
                    },
                    writing_guidance=["Introduce the challenge before naming the module."],
                )
            ],
        )
    )
    state.apply_summary(
        SummaryChunk(
            domain="remote photoplethysmography",
            purpose="Help write papers.",
            section_expressions={},
            concept_threads=[
                ConceptThread(
                    concept="Motion Artifact Suppression",
                    aliases=["motion-induced noise"],
                    section_roles={"experiments": ["Validates the module through ablation studies."]},
                    writing_guidance=["Connect ablation gains back to motion robustness."],
                )
            ],
        )
    )

    thread = state.concept_threads[0]
    assert thread.concept == "motion artifact suppression"
    assert thread.aliases == ["motion artifacts", "motion-induced noise"]
    assert sorted(thread.section_roles) == ["experiments", "introduction", "method"]
    assert len(thread.writing_guidance) == 2
