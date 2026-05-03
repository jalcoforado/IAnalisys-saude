"""
Modelos da camada ANALYTICS — dimensões e fatos para dashboards e IA.

dim_*  → entidades pré-formatadas para JOINs (calendário, paciente, profissional)
fato_* → eventos quantitativos com FK lógica para dimensões
"""
from sqlalchemy import (
    Boolean, Column, Date, Index, Integer, String
)
from app.db.base import Base


class DimTempo(Base):
    """
    Dimensão de calendário. 1 linha por dia, populada proceduralmente.
    Não tem tenant_id (calendário é universal).
    """
    __tablename__ = "dim_tempo"
    __table_args__ = (
        Index("ix_dim_tempo_year_month", "year", "month"),
        Index("ix_dim_tempo_year_month_key", "year_month_key"),
        Index("ix_dim_tempo_year_quarter_key", "year_quarter_key"),
    )

    date_key = Column(Date, primary_key=True)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)   # 1=dom .. 7=sáb (DAYOFWEEK MySQL)
    day_of_year = Column(Integer, nullable=False)
    year_month_key = Column(String(7), nullable=False)        # 'YYYY-MM'
    year_quarter_key = Column(String(7), nullable=False)      # 'YYYY-Q1'
    is_weekend = Column(Boolean, nullable=False)
    month_name_pt = Column(String(20), nullable=False)
    day_of_week_name_pt = Column(String(20), nullable=False)
