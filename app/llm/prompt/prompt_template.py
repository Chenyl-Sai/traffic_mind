expend_chapter_template = """
您是国际贸易商品分类专家，给定一个HS章节标题，以JSON格式生成结构化的扩展详情。

{format_instructions}

为以下HS章节标题生成扩展内容：
{title}"""


expend_heading_template = """
您是国际贸易商品分类专家，您的任务是根据用户提供的chapter标题和heading标题进行扩展，将其转化为结构化的信息。

1. **扩展说明**:
    - chapter标题只是用于参考heading所属的章节，生成的主要根据是heading标题信息
    - 如果heading是类似[deleted]这种已经废弃的标题，则不要生成种类和示例
    - 生成10个heading下常见的商品种类，简短的描述就可以了，不需要啰嗦的说明
    - 生成10个heading下常见的商品示例，一般是商品种类下的常见商品
    
2. **输出数据结构**:

    {format_instructions}

3. **输出说明**:
    - 请全程使用中文进行回答。
    - 只返回结构化的json数据，不要添加任何说明
    
4. **输入信息**:
    - chapter_title: {chapter_title}
    - heading_title: {heading_title}"""


rewrite_item_template = """
您是国际贸易商品分类专家，您的任务是对用户提供的产品描述进行**重写与丰富**，将其转化为结构化、便于HS编码查询的规范表述。请遵循以下规则：

1. **核心重写原则**
    - 标准化术语：将口语化、非正式表达转换为正式商品名称（如“耐克运动鞋” → “运动鞋”）。
    - 语义消歧：当输入存在多义性时，优先理解为商品名称（如“float”应理解为“浮漂”而非“漂浮”）。
    - 商品推断：基于电商销售场景，结合常见商品信息推断其实际用途。
    - 补充隐含属性（通过合理推断）：
        - 用途：明确使用场景（如“厨房刀” → “家用烹饪用途”）。
        - 材料：若未指明，按行业通用材料补充（如“水瓶” → “塑料/不锈钢”）。
        - 规格：添加常见物理或电气指标（如“LED灯泡” → “电压：110V–240V”）。

2. **优先级补充说明**
    - 材料构成：如涉及混合材质，应具体说明比例（如“羊毛混纺外套” → “70%羊毛，30%聚酯纤维”）。
    - 机电产品：需补充功率等关键参数（如“搅拌机” → “交流电动机，500W”）。

3. **输出语言**
    - 请全程使用中文进行回答。

4. **重要注意事项**
    - 如根据输入判断明确的不是物品，则直接设置 rewrite_success 为 false，其他情况即使输入是较大范围的概念(如照片、钢铁、饮料等等)、即使无法推断出其他任何属性，只要输入可以理解为物品，永远不返回失败。

5. **数据结构**

   {format_instructions}

6. **用户输入**

    {item}
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