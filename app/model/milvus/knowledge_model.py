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
    content_vector: list[float] | None = Field(title="内容向量", description="内容向量", default=None)

class HeadingKnowledge(BaseModel):
    """
    类目知识
    """
    heading_code: str = Field(title="类目编码", description="类目编码")
    heading_title: str = Field(title="类目标题", description="类目标题")
    heading_includes: list[str] | None = Field(title="常见商品子类", description="常见商品子类", default=None)
    heading_common_examples: list[str] | None = Field(title="常见商品例子", description="常见商品例子", default=None)
    heading_description: str = Field(title="类目描述", description="heading_title+heading_includes+heading_common_examples")
    heading_description_vector: list[float] = Field(title="类目描述向量", description="类目描述向量")
    chapter_code: str = Field(title="所属章节编码", description="所属章节编码")
    chapter_title: str = Field(title="章节标题", description="章节标题")
    chapter_description: str = Field(title="章节内容", description="章节所有信息拼接的json汇总")
