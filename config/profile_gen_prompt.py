SEMANTIC_PROFILE_GEN_TEMPLATE = """
You are a rubric-driven educational measurement specialist (psychometrician) with expertise in assessment design, content validity, and inter-rater reliability. Your job is to create a <semantic_profile> based on the given <passage>.

**Instructions:**
Build a <semantic_profile> for the following <passage>. Extract all items listed below.

**<passage>:**
{var_passage_text}
---

**1) discipline:**
Categorize the <passage> into one of the following disciplines:
a. People, Society & Culture (People, behavior, emotions, relationships, community, history/civics, global issues, arts, food, clothing, religion, holidays/special days, life experiences.)
b. Learning & Work (School life, learning skills/habits, careers.)
c. Geography & Places (Natural Environments, continents, countries/regions, cities/landmarks.)
d. Nature & Earth Systems (Animals, insects, plants, ecosystems/biomes, seasons & weather.)
e. Science, Space & Technology (General science, engineering/tech, transportation/vehicles, space/solar system.)
f. Health, Risk & Adventure (Health/medical, safety/disasters, sports/recreation, activities & outdoor/adventure.)

**2) subtopic_1:**
Categorize the <passage> into one of the following subtopics. Choose the best subtopic for the overall content of the passage:
Activities, Adventure, Animals, Arts, Behavior, Careers, Clothing and Dress, Community Life, Continents, Classics, Character Traits, Diaries/Journals/Letters/Blogs, Disasters, Emotions, Food, Family Life, Fairy Tales, Fantasy/Imagination, Folklore/Fables/Myths, Holidays, Health & Wellness, Historical Fiction, Natural Environments, People, Places, Plants, Poetry/Rhymes, School, Science, Science Fiction, Seasons/Weather, Special Occasions, Sports/Recreation, Technology, Transportation/Vehicles, Universe/Solar System

**3) central_focus:**
Give around five words or short phrases (two words max) that describe the main sections or paragraphs of the <passage>. Example: "landforms," "temperature zones," "wildlife," "daylight extremes."

**4) key_concepts:**
Give around fifteen terms that are distinctive anchors in the <passage>. These can include named entities, proper nouns, dates, formulas, definitions, data points, or key terminology.

**5) processes_structures:**
Describe any procedures, causal chains, proof steps, plot arcs, or argument structures (e.g., hook-body-conclusion) present in the passage.

**6) setting_context:**
Describe the time, place, population, or constraints relevant to the passage.

**7) purpose/objective:**
Identify the primary purpose of the passage from the following options: explain, describe, entertain, compare, argue.

**8) genre/form:**
Identify the genre or form of the passage from the following options: expository, narrative, procedural, argumentative, fiction, fairytale.
"""

SUBTOPIC2_GEN_TEMPLATE = """
You are an AI assistant specializing in categorical analysis. Your task is to identify the correct `subtopic_2` based on the provided information.

**Instructions:**
Analyze the following semantic profile, which was extracted from the passage. Based on all the provided clues(`subtopic_1`, `central_focus`, and `key_concepts`), select the single most appropriate `subtopic_2` from the options list.

**<passage summary>:**
{var_passage_summary}

**<ar_category_data>:**
{var_relevant_ar_category_data}

Your response should only be the name of the `subtopic_2`.
"""