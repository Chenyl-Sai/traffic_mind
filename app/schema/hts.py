from pydantic import BaseModel, Field

# 检查更新相应参数
class CheckUpdateResponse(BaseModel):
    current_version: str = Field(default="")
    lastest_version: str = Field(default="")
    need_update: bool = Field(default=False)
    updating: bool = Field(default=False)
    message: str = Field(default="")

class HtsRecordFootnote(BaseModel):
    columns: list[str] = Field(title="此脚注所说明的列")
    marker: str | None = Field(title="标记", default=None)
    value: str = Field(title="脚注的说明")
    type: str = Field(title="脚注类型", description="endnote/footnote")

class HtsRecord(BaseModel):
    htsno: str = Field(title="HTS编码", description="有时候是空的")
    indent: int = Field(title="缩进层级", description="从0开始")
    description: str = Field(title="描述", description="")
    superior: bool | None = Field(title="是否父级", default=None, description="如果是父级，则htsno为空")
    units: list[str] | None = Field(title="可申报单位", description="多个单位逗号分割")
    general: str | None = Field(title="一般税率", description="除了other中的4个国家都适用的税率")
    special: str | None = Field(title="特殊税率", description="根据标注(A+,AU,BH,CL,CO,D,E,IL,JO,KR,MA,OM,P,PA,PE,S,SG)等等指定的税率")
    other: str | None = Field(title="其他税率", description="目前只有朝鲜、古巴、白俄罗斯、俄罗斯四个国家")
    footnotes: list[HtsRecordFootnote] | None = Field(title="脚注", default=None)
    quotaQuantity: str | None = Field(title="配额数量", description="若该商品属于关税配额项目，则此字段记录对应的配额数量", default=None)
    additionalDuties: str | None = Field(title="附加关税", description="一般在99条目中附加", default=None)

class HtsProcessResult(BaseModel):
    success: bool = Field(title="处理结果", default=False)
    message: str = Field(title="处理结果信息", default="")
    failed_row: int = Field(title="处理失败行数", default=0)
    can_resume: bool = Field(title="是否可恢复", default=False)

class HtsInheritanceDequeElement(BaseModel):
    code: str = Field(title="编码", default="")
    description: str = Field(title="描述", default="")
    indent: int = Field(title="缩进层级", default=0)
    is_superior: bool | None = Field(title="是否父级:父级没有编码(编码无意义，不可用于申报)", default=False)
    id: int = Field(title="父级编码", default=0)
    type: int = Field(title="类型-0:rate_line,1:stat_suffix", default=0)
    general: str | None = Field(title="一般税率", description="除了other中的4个国家都适用的税率")
    special: str | None = Field(title="特殊税率", description="根据标注(A+,AU,BH,CL,CO,D,E,IL,JO,KR,MA,OM,P,PA,PE,S,SG)等等指定的税率")
    other: str | None = Field(title="其他税率", description="目前只有朝鲜、古巴、白俄罗斯、俄罗斯四个国家")