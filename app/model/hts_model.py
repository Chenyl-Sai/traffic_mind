from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base

class HtsRateLine(Base):
    """美国HTS税率线编码, HTS中8位编码，用于定义适用税率"""
    __tablename__ = "base_hts_rate_line"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    rate_line_code: Mapped[str] = mapped_column(String(8), index=True, nullable=True, comment="汇率编码")
    rate_line_description: Mapped[str] = mapped_column(String(2000), nullable=False, comment="汇率描述")
    general_rate: Mapped[str] = mapped_column(String(500), nullable=True, comment="通用汇率-最惠国税率")
    special_rate: Mapped[str] = mapped_column(String(500), nullable=True, comment="特殊汇率-根据标注(A+,AU,BH,CL,CO,D,E,IL,JO,KR,MA,OM,P,PA,PE,S,SG)等等指定的税率")
    other: Mapped[str] = mapped_column(String(500), nullable=True, comment="其他汇率-不适用通用税率时的税率，目前只有朝鲜、古巴、白俄罗斯、俄罗斯四个国家")
    units: Mapped[str] = mapped_column(String(200), nullable=True, comment="单位:No./kg etc.")
    quota_quantity: Mapped[str] = mapped_column(String(200), nullable=True, comment="配额数量:若该商品属于关税配额项目，则此字段记录对应的配额数量")
    additional_duties: Mapped[str] = mapped_column(String(200), nullable=True, comment="附加关税:一般在99条目中附加")
    indent: Mapped[int] = mapped_column(Integer, nullable=False, comment="缩进层级")
    is_superior: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="是否父级:父级没有编码(编码无意义，不可用于申报)")
    parent_id: Mapped[int] = mapped_column(Integer, ForeignKey("base_hts_rate_line.id", ondelete="SET NULL"), nullable=True, comment="父级编码")
    children: Mapped[list["HtsRateLine"]] = relationship("HtsRateLine", backref="parent", remote_side=[id], lazy="joined")
    wco_hs_subheading: Mapped[str] = mapped_column(String(10), nullable=True, comment="WCO HS子目")
    version: Mapped[str] = mapped_column(String(50), comment="更新版本: 2025 Revision 16", nullable=False)
    is_rate_line: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否8位税率线编码", nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, comment="是json文件中的第几个对象", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

class HtsRateLineFootnote(Base):
    """美国HTS税率线标志信息，一般用户额外豁免/加征补充说明等"""
    __tablename__ = "base_hts_rate_line_foot_note"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    rate_line_id: Mapped[int] = mapped_column(Integer, ForeignKey("base_hts_rate_line.id", ondelete="CASCADE"), index=True, nullable=False, comment="所属税率线")
    related_column: Mapped[str] = mapped_column(String(200), comment="关联税率线中的列:['general', 'stat', 'units']", nullable=False)
    note_value: Mapped[str] = mapped_column(String(1000),comment="标志值", nullable=False)
    note_type: Mapped[str] = mapped_column(String(50), comment="标志类型:endnote/footnote", nullable=False)
    marker: Mapped[str] = mapped_column(String(50), comment="标记，目前不知道什么作用，当note_type为footnote的时候值为1，其他时候都为空", nullable=True)
    row_index: Mapped[int] = mapped_column(Integer, comment="是json文件中的第几个对象", nullable=False)
    version: Mapped[str] = mapped_column(String(50), comment="更新版本: 2025 Revision 16", nullable=False)
    create_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    update_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

class HtsStatSuffix(Base):
    """美国HTS统计后缀，10位编码，仅适用于分类及统计使用"""
    __tablename__ = "base_hts_stat_suffix"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    stat_code: Mapped[str] = mapped_column(String(10), index=True, unique=True, nullable=False, comment="统计后缀编码")
    stat_description: Mapped[str] = mapped_column(String(2000), index=True, nullable=False, comment="统计后缀描述")
    indent: Mapped[int] = mapped_column(Integer, nullable=False, comment="缩进层级")
    is_superior: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="是否父级:父级没有编码(编码无意义，不可用于申报)")
    rate_line_id: Mapped[int] = mapped_column(Integer, ForeignKey("base_hts_rate_line.id", ondelete="CASCADE"), nullable=False, comment="所属费率线")
    rate_parent_id: Mapped[int] = mapped_column(Integer, ForeignKey("base_hts_rate_line.id", ondelete="CASCADE"), nullable=True, comment="在费率线标重的父级编码")
    row_index: Mapped[int] = mapped_column(Integer, comment="是json文件中的第几个对象", nullable=False)
    version: Mapped[str] = mapped_column(String(50), comment="更新版本: 2025 Revision 16", nullable=False)
    create_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    update_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

class HtsUpdateRecord(Base):
    __tablename__ = "base_hts_update_record"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    update_version: Mapped[str] = mapped_column(String(50), comment="更新版本: 2022", nullable=False)
    update_status: Mapped[str] = mapped_column(String(50), comment="更新结果: doing/success/fail", nullable=False)
    fail_message: Mapped[str] = mapped_column(String(2000), comment="更新失败原因", nullable=True)
    fail_row: Mapped[int] = mapped_column(Integer, comment="更新失败行数", nullable=True)
    can_continue: Mapped[bool] = mapped_column(Boolean, comment="是否可以继续更新", nullable=True)
    create_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    finish_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, comment="更新完成时间")

class HtsVersionHistory(Base):
    __tablename__ = "base_hts_version_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(length=20), comment="版本号", nullable=False)
    is_current_used: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否是当前使用的版本启用")
    enabled_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    disabled_time: Mapped[datetime] = mapped_column(DateTime, default=None, nullable=True)
    create_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    update_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)