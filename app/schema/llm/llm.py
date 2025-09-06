from pydantic import BaseModel, Field


class ChapterExtends(BaseModel):
    """
    这是对海关编码HS系统中Chapter说明的补充信息
    """
    chapter_title: str = Field(title="章节标题",
                               description="入参章节说明信息，如Nuclear reactors, boilers, machinery and mechanical appliances; parts thereof")
    includes: list[str] = Field(title="可能包含的常见商品子类",
                                description="可能包含的商品种类信息，如air conditioners, washing machines, electric pumps, mechanical arms, printing devices")
    common_examples: list[str] = Field(title="常见商品实例",
                                       description="常见商品实例，如laptops, dishwashers, vacuum pumps, etc.")


class HeadingExtends(BaseModel):
    """
    这是对海关编码HS系统中Chapter说明的补充信息
    """
    chapter_title: str = Field(title="章节标题",
                               description="入参章节说明信息，如Nuclear reactors, boilers, machinery and mechanical appliances; parts thereof")
    heading_title: str = Field(title="类目标题",
                               description="入参类目说明信息，如Automatic data processing machines and units thereof; magnetic or optical readers, machines for transcribing data onto data media in coded form and machines for processing such data, not elsewhere specified or included.")
    includes: list[str] | None = Field(title="可能包含的常见商品子类",
                                       description="可能包含的商品种类信息，如Personal computers, Storage units, Input units, Output units, Data processing peripherals",
                                       default=None)
    common_examples: list[str] | None = Field(title="常见商品实例",
                                              description="常见商品实例，如laptops, HDD, SSD, keyboards, printers, USB flash drives, etc.",
                                              default=None)


class ItemRewriteResponse(BaseModel):
    """
    商品重写结果
    """
    rewrite_success: bool = Field(title="重写成功与否",
                                  description="商品重写成功与否, 只有在输入不是物品时才返回false，其他情况返回true")
    name: str | None = Field(title="商品名称",
                             description="商品名称，如果不是字符串自动改写成字符串，如未提取到则重写失败，除非改写失败，否则必须返回",
                             default=None)
    en_name: str | None = Field(title="商品英文名称",
                                description="直接翻译输入的商品名称为中文，如果输入是英文，则不翻译，直接返回原始数据，除非改写失败，否则必须返回",
                                default=None)
    cn_name: str | None = Field(title="商品中文名称",
                                description="直接翻译输入的商品名称为中文，如果输入是中文，则不翻译，直接返回原始数据，除非改写失败，否则必须返回",
                                default=None)
    classification_name_cn: str | None = Field(title="商品归类名称",
                                               description="简短的归类名称，比如各种纸轴棉签、木轴棉签、竹制棉签等等，简短归类到棉签",
                                               default=None)
    classification_name_en: str | None = Field(title="商品归类英文名称",
                                               description="简短的归类英文名称",
                                               default=None)
    brand: str | None = Field(title="商品品牌", description="如有提及或可通过品类推断", default='无品牌')
    materials: str | None = Field(title="商品材质", description="主要材料及占比，如80%棉+20%聚酯纤维", default=None)
    purpose: str | None = Field(title="商品用途", description="消费场景/功能，如家用，工业用，宠物用，医用等", default=None)
    specifications: str | None = Field(title="商品规格", description="尺寸/重量/容量/功率等物理特性", default=None)
    processing_state: str | None = Field(title="加工状态", description="是否组装、是否为半成品、加工工艺等", default=None)
    special_properties: str | None = Field(title="特殊属性", description="是否带电、是否含有液体、是否可食用等",
                                           default=None)
    other_notes: str | None = Field(title="其他说明", description="任何其他可能影响分类的有用信息", default=None)


class HeadingDetermineResponseDetail(BaseModel):
    """
    选择此类目的原因及置信度等信息
    """
    heading_code: str = Field(title="类目编码", description="类目编码,入参之一，直接返回")
    heading_title: str = Field(title="类目标题", description="类目标题，入参之一，直接返回")
    reason: str = Field(title="选择此类目的原因", description="选择此类目的简单的依据说明")
    confidence_score: float = Field(title="选择此类目的置信度",
                                    description="数值在0-100之间，商品所属类目概率越大数值越大",
                                    default=0.0)


class HeadingDetermineResponse(BaseModel):
    """
    根据商品信息选择置信度最高的类目，以及候选类目
    """
    alternative_headings: list[HeadingDetermineResponseDetail] = Field(title="商品可能所属的heading列表",
                                                                       description="返回至少10个heading，按照置信度从高到低排列")


class SubheadingDetermineResponseDetail(BaseModel):
    """
    选择此子目的原因及置信度等信息
    """
    subheading_code: str = Field(title="子目编码", description="子目编码,入参之一，直接返回")
    subheading_title: str = Field(title="子目标题", description="子目标题，入参之一，直接返回")
    reason: str = Field(title="选择此子目的原因", description="选择此子目的简单的依据说明", default=None)
    confidence_score: float = Field(title="选择此子目的置信度",
                                    description="数值在0-10之间，商品所属子目概率越大数值越大",
                                    default=0.0)


class SubheadingDetermineResponse(BaseModel):
    """
    根据商品信息选择置信度最高的子目，以及候选子目
    """
    main_subheading: SubheadingDetermineResponseDetail | None = Field(title="置信度最高的子目",
                                                                      description="置信度最高的一个子目", default=None)
    alternative_subheadings: list[SubheadingDetermineResponseDetail] | None = Field(title="其他备选子目",
                                                                                    description="返回至少3个至多5个备选subheading",
                                                                                    default=None)
    reason: str | None = Field(title="未正确分类的原因", description="所有给定subheading列表都不满足时，给出不满足原因",
                               default=None)


class RateLineDetermineResponse(BaseModel):
    """
    最终选择的税率线的结果
    """
    rate_line_code: str | None = Field(title="税率线编码", description="税率线编码,入参之一，直接返回", default=None)
    rate_line_title: str | None = Field(title="税率线标题", description="税率线标题，入参之一，直接返回", default=None)
    reason: str | None = Field(title="选择此税率线的原因", description="选择此税率线的简单的依据说明", default=None)
    confidence_score: float | None = Field(title="选择此税率线的置信度",
                                           description="数值在0-10之间，商品所属税率线概率越大数值越大",
                                           default=0.0)
    disqualification_others_reason: str | None = Field(title="弃选其他选项原因",
                                                       description="未选择其他提供的rate_line的原因说明",
                                                       default=None)
    fail_reason: str | None = Field(title="失败原因",
                                    description="当所有税率线都不满足条件时返回此字段，否则不用返回此字段",
                                    default=None)


class GenerateFinalOutputResponse(BaseModel):
    """
    最终生成的输出结果
    """
    rate_line_code: str = Field(title="税率线编码", description="总结输出最终确定的税率编码")
    final_output_reason: str = Field(title="生成最终输出的原因", description="总结最终选择此税率线的原因,1800字以内")
