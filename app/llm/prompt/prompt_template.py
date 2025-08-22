expend_chapter_template = """
You are an expert in HS (Harmonized System) code classification. Given an HS chapter heading, generate structured expansion details in JSON format.

{format_instructions}

Generate the expansion for the following HS chapter heading:
{title}"""


rewrite_item_template = """
You are an expert in international trade commodity classification. Your task is to **rewrite and enrich** user-provided product descriptions into structured, HS Code-friendly information by:

1. Core Rewriting Rules
    Standardize Terminology: Convert colloquial terms to formal product names (e.g., "Nike sneakers" → "athletic shoes").
    Infer Missing Attributes: Fill in gaps logically:
        Purpose: Deduce usage (e.g., "kitchen knife" → "household culinary use").
        Material: Default to industry-common materials if unspecified (e.g., "water bottle" → "plastic/stainless steel").
        Specifications: Add implied metrics (e.g., "LED bulb" → "voltage: 110V-240V").
    Resolve Ambiguities: Request user clarification only if critical (e.g., "organic cotton shirt" with "waterproof coating" → ask if coated post-weaving).
2. Priority Inferences
    Material Hierarchy: List materials by dominance (e.g., "wool blend coat" → "70% wool, 30% polyester").
    Electronics/Mechanics: Always infer power specs (e.g., "blender" → "AC motor, 500W").
    Agricultural Goods: State processing level (e.g., "coffee beans" → "roasted, not decaffeinated").
3. All information are written in english. 
4. When the input content detection result is not a product, **do not return the need_other_messages field! Directly return rewrite_success as false!**
    
{format_instructions}

Here is the product description:
{item}
"""


determine_chapter_template = """
As a seasoned expert in international trade commodity classification, your task is to analyze the provided product description and determine the most appropriate Harmonized System (HS) chapter classification based on the given chapter list. Your analysis should include:

1. **Chapter Determination**: Identify the most relevant HS chapter for the product.
2. **Rationale**: Provide a detailed explanation supporting your classification decision, referencing specific product characteristics and chapter criteria.
3. **Confidence Score**: Assess your confidence in the classification (e.g., 0-10) with justification.
4. **Alternative Considerations**: Mention any borderline cases or alternative chapters considered, if applicable.

**Constraints**:
    For multi-material products, try to retain multiple material-related categories. For example, for paper shaft cotton swabs, keep both paper-related and cotton-related categories to avoid only retaining the paper category and then finding that all paper categories do not match and missing the cotton category.

**Chapter Scope**:
{chapter_list}

**Output Format**: 
{format_instructions}

**Product Description**:
{item}

Please provide your analysis in JSON format as specified, ensuring clarity and precision in your classification.
"""

determine_heading_template = """
You are an expert in international trade commodity classification. Based on the product description provided, analyze the item and assign the most appropriate HS Code heading from the given scope. Strictly follow the requirements and output in the specified JSON format.

**Task Requirements**:
    Analyze key attributes of the product (e.g., material, function, intended use).
    Select the best-matched 4-digit heading from the provided list.
    Include all specified fields in the output (see Output Format):
        selected_heading: Final 4-digit HS code (highest confidence).
        basis: Brief justification (≤50 characters).
        confidence: Match accuracy score (0-10, 10=perfect match).
        candidates: Top 3 candidate headings (descending order) with reasons.

**Constraints**:
    Return null if the product clearly does not belong to any provided heading.
    Strictly use only the user-provided heading list.
    For multi-material products, try to retain multiple material-related categories. For example, for paper shaft cotton swabs, keep both paper-related and cotton-related categories to avoid only retaining the paper category and then finding that all paper categories do not match and missing the cotton category.
    You need to pay attention not only to the information in heading_title, but also to the description in the chapter to which it belongs (the key of the dictionary where the heading list is located is the chapter to which it belongs)

**Heading Scope**：
{heading_list}

**Output Format**: 
{format_instructions}

**Product Description**:
{item}

Please provide your analysis in JSON format as specified, ensuring clarity and precision in your classification.
"""

determine_subheading_template = """
You are an expert in international trade commodity classification. Based on the product description provided, analyze the item and assign the most appropriate HS Code subheading from the given scope. Strictly follow the requirements and output in the specified JSON format.

**Task Requirements**:
    Analyze key attributes of the product (e.g., material, function, intended use).
    Select the best-matched 6-digit subheading from the provided list.
    Include all specified fields in the output (see Output Format):
        selected_subheading: Final 6-digit HS code (highest confidence).
        basis: Brief justification (≤50 characters).
        confidence: Match accuracy score (0-10, 10=perfect match).
        candidates: Top 3 candidate subheadings (descending order) with reasons.

**Constraints**:
    Return null if the product clearly does not belong to any provided heading.
    Strictly use only the user-provided subheading list.
    For multi-material products, try to retain multiple material-related categories. For example, for paper shaft cotton swabs, keep both paper-related and cotton-related categories to avoid only retaining the paper category and then finding that all paper categories do not match and missing the cotton category.
    You need to pay attention not only to the information in subheading scope, but also to the description in the chapter and heading to which it belongs (the key of the dictionary where the subheading list is located is the chapter and heading to which it belongs)
    Note that in subheading scope, although the encoding does not have a clear hierarchy, there is still an obvious hierarchy based on the number of '-'s in the description prefix. For example, the upper level of two '-'s is to find the subheading with the nearest '-'. If necessary, the number of '-'s should be used to determine the hierarchy, especially when the subheading contains many "Others" categories.

**Subheading Scope**：
{subheading_list}

**Output Format**: 
{format_instructions}

**Product Description**:
{item}

Please provide your analysis in JSON format as specified, ensuring clarity and precision in your classification.
"""

determine_rate_line_template = """
You are an expert in international trade commodity classification. Based on the product description provided, analyze the item and assign the most appropriate HTS Rate Line from the given scope. Strictly follow the requirements and output in the specified JSON format.

**Task Requirements**:
    Analyze key attributes of the product (e.g., material, function, intended use).
    Select the best-matched 8-digit rate line  from the provided scope.
    Include all specified fields in the output (see Output Format):
        selected_rate_line: Final 8-digit HTS rate line code (highest confidence).
        basis: Brief justification (≤50 characters).
        confidence: Match accuracy score (0-10, 10=perfect match).

**Constraints**:
    Return null if the product clearly does not belong to any provided heading.
    Strictly use only the user-provided rate line scope.

**Rate Line Scope**：
{rate_line_list}

**Output Format**: 
{format_instructions}

**Product Description**:
{item}

Please provide your analysis in JSON format as specified, ensuring clarity and precision in your classification.
"""

generate_final_output_template = """
You are a customs classification expert.
I will provide you with the full decision-making process of how a product was classified from its original description to its final rate line code. This includes the candidates considered at each layer and the reasons for the selections.
Your task is to generate a **summary explanation** that clearly states why the product was ultimately classified under this rate line code.
**Important instructions**:
    - Base your explanation strictly on the decision process I provide. Do not introduce additional assumptions or external information.
    - The output should be formal, clear, logically structured, and suitable for classification documentation.
    - Emphasize the logical consistency of the choices made at each level and the overall appropriateness of the final code.

Here is the decision process:
    Original product description: {original_item}
    Rewritten product description: {rewritten_item}

**Decision Process**
    Chapter candidates: {chapter_candidates}
        Selected: {selected_chapter}
        Reason: {reason_chapter}
    
    Heading candidates: {heading_candidates}
        Selected: {selected_heading}
        Reason: {reason_heading}
    
    Subheading candidates: {subheading_candidates}
        Selected: {selected_subheading}
        Reason: {reason_subheading}
    
    Rate line candidates: {rate_line_candidates}
        Selected: {selected_rate_line}
        Reason: {reason_rate_line}
    
    Final Result
        Rate line code: {final_code}

{format_instructions}
"""