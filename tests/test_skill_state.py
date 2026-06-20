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
    state = SkillState(domain="natural language processing")

    state.apply_summary(
        SummaryChunk(
            domain="natural language processing",
            purpose="Help write papers.",
            section_expressions={},
            concept_threads=[
                ConceptThread(
                    concept="retrieval augmentation",
                    aliases=["retrieval-augmented generation"],
                    section_roles={
                        "introduction": ["Frames missing knowledge as a key reliability challenge."],
                        "method": ["Links retrieval augmentation to grounding modules."],
                    },
                    writing_guidance=["Introduce the knowledge gap before naming the module."],
                )
            ],
        )
    )
    state.apply_summary(
        SummaryChunk(
            domain="natural language processing",
            purpose="Help write papers.",
            section_expressions={},
            concept_threads=[
                ConceptThread(
                    concept="Retrieval Augmentation",
                    aliases=["external evidence retrieval"],
                    section_roles={"experiments": ["Validates the module through ablation studies."]},
                    writing_guidance=["Connect ablation gains back to grounded generation."],
                )
            ],
        )
    )

    thread = state.concept_threads[0]
    assert thread.concept == "retrieval augmentation"
    assert thread.aliases == ["retrieval-augmented generation", "external evidence retrieval"]
    assert sorted(thread.section_roles) == ["experiments", "introduction", "method"]
    assert len(thread.writing_guidance) == 2
