"""
hts编码分类相关的缓存数据
"""
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.core.db import Base

class ItemRewriteCache(Base):
    """商品改写缓存数据"""
    __tablename__ = "hts_classify_cache_item_rewrite"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    origin_item_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="原始商品名称")
    is_real_item: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="是否是真正的商品名称")
    rewritten_item: Mapped[dict] = mapped_column(JSONB, nullable=True, comment="商品改写结果")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class HtsClassifyE2ECache(Base):
    """HTS分类端到端缓存"""
    __tablename__ = "hts_classify_cache_e2e"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    origin_item_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="原始商品名称")
    name_cn: Mapped[str] = mapped_column(String(200), nullable=True, comment="商品名称")
    name_en: Mapped[str] = mapped_column(String(200), nullable=True, comment="商品英文名称")
    classification_name_cn: Mapped[str] = mapped_column(String(200), nullable=True, comment="商品归类名称")
    classification_name_en: Mapped[str] = mapped_column(String(200), nullable=True, comment="商品英文归类名称")
    brand: Mapped[str] = mapped_column(String(200), nullable=True, comment="商品品牌")
    material: Mapped[str] = mapped_column(String(500), nullable=True, comment="商品材质")
    purpose: Mapped[str] = mapped_column(String(500), nullable=True, comment="商品用途")
    specifications: Mapped[str] = mapped_column(String(500), nullable=True, comment="商品规格")
    processing_state: Mapped[str] = mapped_column(String(500), nullable=True, comment="商品加工状态")
    special_properties: Mapped[str] = mapped_column(String(500), nullable=True, comment="商品特殊属性")
    other_notes: Mapped[str] = mapped_column(String(500), nullable=True, comment="商品其他说明")
    chapter_code: Mapped[str] = mapped_column(String(200), nullable=True, comment="商品章节编码")
    chapter_title: Mapped[str] = mapped_column(String(2000), nullable=True, comment="商品章节标题")
    chapter_reason: Mapped[str] = mapped_column(String(2000), nullable=True, comment="商品章节选择原因")
    heading_code: Mapped[str] = mapped_column(String(200), nullable=True, comment="商品类目编码")
    heading_title: Mapped[str] = mapped_column(String(2000), nullable=True, comment="商品类目标题")
    heading_reason: Mapped[str] = mapped_column(String(2000), nullable=True, comment="商品类目选择原因")
    subheading_code: Mapped[str] = mapped_column(String(200), nullable=True, comment="商品子目编码")
    subheading_title: Mapped[str] = mapped_column(String(2000), nullable=True, comment="商品子目标题")
    subheading_reason: Mapped[str] = mapped_column(String(2000), nullable=True, comment="商品子目选择原因")
    rate_line_code: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品税率线编码")
    rate_line_title: Mapped[str] = mapped_column(String(2000), nullable=False, comment="商品税率线标题")
    rate_line_reason: Mapped[str] = mapped_column(String(2000), nullable=True, comment="商品税率线选择原因")
    final_output_reason: Mapped[str] = mapped_column(String(2000), nullable=False, comment="商品最终输出原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
