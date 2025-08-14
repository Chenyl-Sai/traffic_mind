from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class WcoHsSection(Base):
    """WCO通用HS分类"""
    __tablename__ = "base_wco_hs_section"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    section_code: Mapped[str] = mapped_column(String(2), index=True, unique=True, nullable=False, comment="分类编码")
    section_title: Mapped[str] = mapped_column(String(2000), nullable=False, comment="分类标题")
    version: Mapped[str] = mapped_column(String(50), comment="更新版本")
    load_children_url: Mapped[str] = mapped_column(String(200), nullable=True, comment="加载子级数据的url")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    chapters: Mapped[list["WcoHsChapter"]] = relationship("WcoHsChapter", back_populates="section")


class WcoHsChapter(Base):
    """WCO通用HS章节"""
    __tablename__ = "base_wco_hs_chapter"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    chapter_code: Mapped[str] = mapped_column(String(2), index=True, unique=True, comment="章节编码")
    chapter_title: Mapped[str] = mapped_column(String(2000), comment="章节编码")
    load_children_url: Mapped[str] = mapped_column(String(200), nullable=True, comment="加载子级数据的url")
    section_id: Mapped[int] = mapped_column(Integer, ForeignKey("base_wco_hs_section.id", ondelete="CASCADE"),
                                            nullable=False, comment="所属分类")
    version: Mapped[str] = mapped_column(String(50), comment="更新版本")
    section: Mapped["WcoHsSection"] = relationship("WcoHsSection", back_populates="chapters")
    headings: Mapped[list["WcoHsHeading"]] = relationship("WcoHsHeading", back_populates="chapter")


class WcoHsHeading(Base):
    """WCO通用HS品目"""
    __tablename__ = "base_wco_hs_heading"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    heading_code: Mapped[str] = mapped_column(String(4), index=True, unique=True, comment="标题编码")
    heading_title: Mapped[str] = mapped_column(String(2000), comment="标题")
    load_children_url: Mapped[str] = mapped_column(String(200), nullable=True, comment="加载子级数据的url")
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("base_wco_hs_chapter.id", ondelete="CASCADE"),
                                            nullable=False, comment="所属章节")
    version: Mapped[str] = mapped_column(String(50), comment="更新版本")
    chapter: Mapped["WcoHsChapter"] = relationship("WcoHsChapter", back_populates="headings")
    subheadings: Mapped[list["WcoHsSubheading"]] = relationship("WcoHsSubheading", back_populates="heading")


class WcoHsSubheading(Base):
    """WCO通用HS子品目"""
    __tablename__ = "base_wco_hs_subheading"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    subheading_code: Mapped[str] = mapped_column(String(6), index=True, unique=True, comment="子标题编码")
    subheading_title: Mapped[str] = mapped_column(String(2000), comment="子标题")
    heading_id: Mapped[int] = mapped_column(Integer, ForeignKey("base_wco_hs_heading.id", ondelete="CASCADE"),
                                            nullable=False, comment="所属标题")
    version: Mapped[str] = mapped_column(String(50), comment="更新版本")
    heading: Mapped["WcoHsHeading"] = relationship("WcoHsHeading", back_populates="subheadings")


class WcoHsUpdateRecord(Base):
    __tablename__ = "base_wco_hs_update_record"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    update_version: Mapped[str] = mapped_column(String(50), comment="更新版本: 2022", nullable=False)
    update_status: Mapped[str] = mapped_column(String(50), comment="更新结果: doing/success/fail", nullable=False)
    fail_message: Mapped[str] = mapped_column(String(2000), comment="更新失败原因", nullable=True)
    failed_section: Mapped[str] = mapped_column(String(50), comment="更新失败的分类", nullable=True)
    failed_chapter: Mapped[str] = mapped_column(String(50), comment="更新失败的章节", nullable=True)
    failed_heading: Mapped[str] = mapped_column(String(50), comment="更新失败的目", nullable=True)
    can_continue: Mapped[bool] = mapped_column(Boolean, comment="是否可以继续更新", nullable=True)
    create_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    finish_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, comment="更新完成时间")


class WcoHsVersionHistory(Base):
    __tablename__ = "base_wco_hs_version_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(length=20), comment="版本号")
    is_current_used: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否是当前使用的版本启用")
    enabled_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    disabled_time: Mapped[datetime] = mapped_column(DateTime, default=None, nullable=True)
    create_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    update_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
