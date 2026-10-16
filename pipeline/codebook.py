"""Question metadata for the survey.

The raw file uses the full question text as column names. The codebook maps each raw column to
a short id, a readable label, a question type and the order its answers should be shown in.
It is also the allowlist of columns the API is allowed to query.
"""

from dataclasses import dataclass

AGREE_SCALE = (
    "Agree strongly",
    "Agree slightly",
    "Neither agree nor disagree",
    "Disagree slightly",
    "Disagree strongly",
    "Don't know",
)
YES_NO = ("Yes", "No")


@dataclass(frozen=True)
class Question:
    id: str
    label: str
    group: str
    kind: str  # "id", "numeric", "single", "yes_no" or "agree_scale"
    source: str | None = None  # raw column name, None for derived columns
    options: tuple[str, ...] = ()  # allowed answers, in display order
    base: str = "All respondents"


STATEMENTS = "which_of_the_following_statements_apply_to_you_"
ATTITUDES = "general_attitudes_"


def _statement(id: str, source_suffix: str, label: str, **kwargs) -> Question:
    return Question(
        id, label, "Statements that apply", "yes_no", STATEMENTS + source_suffix, YES_NO, **kwargs
    )


def _attitude(id: str, source_suffix: str, label: str) -> Question:
    return Question(
        id, label, "General attitudes", "agree_scale", ATTITUDES + source_suffix, AGREE_SCALE
    )


QUESTIONS: tuple[Question, ...] = (
    Question("respondent_id", "Respondent ID", "Respondent", "id", "serial_number"),
    # Demographics
    Question(
        "gender",
        "Gender",
        "Demographics",
        "single",
        "gender",
        ("Female", "Male", "Prefer not to say"),
    ),
    Question(
        "age_band",
        "Age band",
        "Demographics",
        "single",
        "age",
        ("18-24", "25-34", "35-44", "45-54", "55-64", "65+"),
    ),
    Question("age", "Age", "Demographics", "numeric", "actual_age"),
    Question(
        "work_status",
        "Working status",
        "Demographics",
        "single",
        "which_of_the_following_best_describes_your_current_working_status",
        (
            "Working full time - working 30 hours per week or more",
            "Working part time - working between 8 and 29 hours per week",
            "Not working/ temporarily unemployed/ sick but seeking work",
            "Not working and not seeking work/ Student",
            "House person, housewife, househusband, etc.",
            "Retired with a private pension",
            "Retired on a state pension only",
        ),
    ),
    Question(
        "region",
        "Region",
        "Demographics",
        "single",
        "which_one_of_these_regions_do_you_live_in",
        (
            "North East",
            "North West",
            "Yorkshire and the Humber",
            "East Midlands",
            "West Midlands",
            "East of England",
            "London",
            "South East",
            "South West",
            "Wales",
            "Scotland",
        ),
    ),
    Question("nation", "Nation", "Demographics", "single", None, ("England", "Scotland", "Wales")),
    Question(
        "income",
        "Household income (before tax)",
        "Demographics",
        "single",
        "what_is_the_combined_annual_income_of_your_household_prior_to_tax_being_deducted",
        (
            "Up to £7,000",
            "£7,001 to £14,000",
            "£14,001 to £21,000",
            "£21,001 to £28,000",
            "£28,001 to £34,000",
            "£34,001 to £41,000",
            "£41,001 to £48,000",
            "£48,001 to £55,000",
            "£55,001 to £62,000",
            "£62,001 to £69,000",
            "£69,001 to £76,000",
            "£76,001 to £83,000",
            "£83,001 or more",
            "Prefer not to answer",
        ),
    ),
    Question(
        "income_group",
        "Household income (grouped)",
        "Demographics",
        "single",
        None,
        ("Up to £21,000", "£21,001 to £41,000", "£41,001 or more", "Prefer not to answer"),
    ),
    Question(
        "employer_type",
        "Type of employer",
        "Demographics",
        "single",
        "work_organisation_please_tell_us_which_type_of_organisation_you_do_or_did_work_for",
        (
            "Private sector firm or company (e.g. limited companies and Plcs)",
            "Self-employed",
            "Other public sector employer (e.g. Central Government)",
            "Nationalised industry or public corporation (e.g. Post Office)",
            "Charity/ voluntary sector",
            "Other",
            "Have never worked",
            "Don't know",
        ),
    ),
    Question(
        "public_sector_area",
        "Public sector area worked in",
        "Demographics",
        "single",
        "do_you_work_in",
        (
            "Education (schools, colleges and universities)",
            "Health and social care",
            "The military",
            "Other",
            "Don't know",
        ),
        base="Public sector and nationalised industry employees",
    ),
    # Politics
    Question(
        "political_interest",
        "Interest in politics",
        "Politics",
        "single",
        "political_interest_how_much_interest_do_you_generally_have_in_what_is_going_on_in_politics",
        ("A great deal", "Quite a lot", "Some", "Not very much", "None at all"),
    ),
    Question(
        "eu_ref_vote",
        "EU referendum vote (2016)",
        "Politics",
        "single",
        "eu_referendum_how_did_you_vote_in_the_eu_referendum_in_june_2016",
        ("Remain", "Leave", "Did not vote / not stated"),
    ),
    Question(
        "vote_intention",
        "General election voting intention",
        "Politics",
        "single",
        "voting_intention_which_party_would_you_vote_for_if_there_was_a_general_election_tomorrow",
        (
            "Conservative",
            "Labour",
            "Liberal Democrat",
            "SNP",
            "Plaid Cymru",
            "Another party",
            "Would not vote",
            "Don't know",
            "Rather not say",
        ),
    ),
    # Statements (multi-select, one Yes/No column per statement)
    _statement("stmt_parents_nearby", "my_parents_live_nearby", "My parents live nearby"),
    _statement(
        "stmt_one_parent_household",
        "i_grew_up_in_a_one_parent_household",
        "I grew up in a one parent household",
    ),
    _statement(
        "stmt_public_transport",
        "i_take_public_transport_regularly",
        "I take public transport regularly",
    ),
    _statement(
        "stmt_manual_labour",
        "i_have_done_manual_labour_work_in_the_past",
        "I have done manual labour work in the past",
    ),
    _statement(
        "stmt_multiple_properties",
        "i_own_more_than_one_property",
        "I own more than one property",
        base="Respondents with an answer (not collected for part of fieldwork)",
    ),
    _statement(
        "stmt_made_redundant",
        "i_have_been_made_redundant_in_my_lifetime",
        "I have been made redundant in my lifetime",
    ),
    _statement(
        "stmt_health_limits_work",
        "i_have_a_health_issue_disability_that_affects_the_jobs_i_can_take",
        "I have a health issue or disability that affects the jobs I can take",
    ),
    _statement(
        "stmt_carer_child",
        "i_care_for_a_child_with_a_serious_health_issue_disability",
        "I care for a child with a serious health issue or disability",
    ),
    _statement(
        "stmt_travel_abroad",
        "i_travel_abroad_regularly_at_least_once_every_year_or_so",
        "I travel abroad regularly (at least once a year or so)",
    ),
    _statement(
        "stmt_work_with_hands",
        "i_predominantly_earn_my_living_using_my_hands_physical_capabilities",
        "I mainly earn my living using my hands or physical capabilities",
    ),
    _statement(
        "stmt_work_with_mind",
        "i_predominantly_earn_a_living_with_my_cognitive_mental_capabilities",
        "I mainly earn my living with my cognitive or mental capabilities",
    ),
    _statement(
        "stmt_great_education",
        "i_had_a_great_education_growing_up",
        "I had a great education growing up",
    ),
    _statement(
        "stmt_uses_excel",
        "i_know_how_to_use_microsoft_excel_spreadsheets",
        "I know how to use Microsoft Excel or spreadsheets",
    ),
    _statement(
        "stmt_lived_london",
        "i_have_lived_in_london_at_some_point_in_my_life",
        "I have lived in London at some point in my life",
    ),
    _statement(
        "stmt_lived_abroad",
        "i_have_worked_or_lived_abroad_in_my_life",
        "I have worked or lived abroad in my life",
    ),
    _statement("stmt_none", "none_of_these", "None of these"),
    # General attitudes (agree / disagree scale)
    _attitude(
        "att_britain_greatest",
        "britain_is_the_greatest_country_in_the_world",
        "Britain is the greatest country in the world",
    ),
    _attitude(
        "att_control_spending",
        "keeping_a_tight_control_over_spending_should_be_the_governments_main_economic_priority",
        "Keeping a tight control over spending should be the government's main economic priority",
    ),
    _attitude(
        "att_tackle_poverty",
        "tackling_poverty_and_inequality_should_be_the_governments_top_priority",
        "Tackling poverty and inequality should be the government's top priority",
    ),
    _attitude(
        "att_partnerships",
        "britain_is_stronger_when_it_forms_partnerships_with_other_countries",
        "Britain is stronger when it forms partnerships with other countries",
    ),
    _attitude(
        "att_defence_cuts",
        "i_worry_that_cuts_in_defence_spending_mean_britain_can_no_longer_defend_itself",
        "I worry that cuts in defence spending mean Britain can no longer defend itself",
    ),
    _attitude(
        "att_control_immigration",
        "the_government_should_prioritise_controlling_immigration_over_all_other_policies",
        "The government should prioritise controlling immigration over all other policies",
    ),
    _attitude(
        "att_welfare_reliance",
        "there_is_too_much_reliance_on_welfare_and_benefits_in_britain_today",
        "There is too much reliance on welfare and benefits in Britain today",
    ),
    _attitude(
        "att_british_first",
        "government_should_always_put_the_needs_of_british_people_ahead_of_others",
        "Government should always put the needs of British people ahead of others",
    ),
    _attitude(
        "att_outward_looking",
        "the_uk_should_be_more_outward_looking_in_nature",
        "The UK should be more outward looking in nature",
    ),
    _attitude(
        "att_working_class", "i_consider_myself_working_class", "I consider myself working class"
    ),
    _attitude(
        "att_big_business",
        "big_business_takes_advantage_of_ordinary_people",
        "Big business takes advantage of ordinary people",
    ),
    # Priorities - options follow the UN Sustainable Development Goal numbering
    Question(
        "top_goal",
        "Most important global goal",
        "Priorities",
        "single",
        "goal_importance_most_important",
        (
            "Eliminating global poverty",
            "Ensuring nobody goes hungry",
            "Good health and well-being",
            "Providing quality education",
            "Gender equality",
            "Providing clean water and sanitation",
            "Making energy affordable and clean",
            "Decent work and economic growth",
            "Industry, innovation, and infrastructure",
            "Reducing inequality between richest and poorest",
            "Making communities and cities sustainable",
            "Responsible consumption and production",
            "Stopping climate change",
            "Conserving the oceans",
            "Conserving life on land",
            "Peace, justice, and strong institutions",
            "Partnerships between countries to achieve these goals",
            "Don't know",
        ),
    ),
)

# Raw columns that are deliberately not loaded
DROPPED_COLUMNS = {
    STATEMENTS + "dont_know": "Answer is 'No' for every respondent, so it carries no information",
}

BY_ID = {q.id: q for q in QUESTIONS}


def source_columns() -> dict[str, str]:
    """Raw column name -> short id, for every question that comes from the raw file."""
    return {q.source: q.id for q in QUESTIONS if q.source}
