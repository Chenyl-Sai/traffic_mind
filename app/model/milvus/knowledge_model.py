from pydantic import BaseModel, Field


class ChapterKnowledge(BaseModel):
    """
    章节知识
    """
    chapter_code: str = Field(title="章节编码", description="章节编码")
    chapter_title: str = Field(title="章节标题", description="章节标题")
    section_code: str = Field(title="所属分类编码", description="所属分类编码")
    includes: list[str] | None = Field(title="常见商品子类", description="常见商品子类", default=None)
    common_examples: list[str] | None = Field(title="常见商品例子", description="常见商品例子", default=None)
    content: str = Field(title="内容", description="上面所有信息拼接的json汇总")

class HeadingKnowledge(BaseModel):
    """
    类目知识
    """
    heading_code: str = Field(title="类目编码", description="类目编码")
    heading_title: str = Field(title="类目标题", description="类目标题")
    chapter_code: str = Field(title="所属章节编码", description="所属章节编码")