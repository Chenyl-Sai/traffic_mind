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

class DetermineChapterCache(Base):
    """章节确定缓存"""
    __tablename__ = "hts_classify_cache_determine_chapter"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    origin_item_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="原始商品名称")
    rewritten_cache_key: Mapped[str] = mapped_column(String(200), nullable=False, comment="改写之后信息的hash key")
    main_chapter: Mapped[dict] = mapped_column(JSONB, nullable=False, comment="主章节结果")
    alternative_chapters: Mapped[list[dict]] = mapped_column(JSONB, nullable=True, comment="候选章节结果")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
