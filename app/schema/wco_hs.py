from pydantic import BaseModel, Field


# 检查更新相应参数
class CheckUpdateResponse(BaseModel):
    current_version: str = Field(default="")
    latest_version: str = Field(default="")
    need_update: bool = Field(default=False)
    updating: bool = Field(default=False)
    message: str = Field(default="")


class WcoHsProcessResult(BaseModel):
    success: bool = Field(title="处理结果", default=False)
    message: str = Field(title="处理结果信息", default="")
    failed_section: str | None = Field(title="处理失败section", default=None)
    failed_chapter: str | None = Field(title="处理失败chapter", default=None)
    failed_heading: str | None = Field(title="处理失败heading", default=None)
    can_resume: bool = Field(title="是否可恢复", default=False)

class WcoHeading(BaseModel):
    heading_code: str = Field(title="类目编码", default="")
    heading_title: str = Field(title="类目标题", default="")
    chapter_code: str = Field(title="所属章节编码", default="")
    chapter_title: str = Field(title="所属章节标题", default="")