from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./agrohub.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def criar_tabelas():
    Base.metadata.create_all(bind=engine)


def migrar_banco():
    migrations = [
        ("contratos_transporte", "valor_frete_saca_final REAL"),
        ("contratos_transporte", "contra_valor_frete REAL"),
        ("ofertas_mercado", "contra_valor_saca REAL"),
        ("ofertas_mercado", "contra_modalidade_venda TEXT"),
        ("ofertas_mercado", "unidade_medida TEXT DEFAULT 'SACAS'"),
        ("ofertas_mercado", "peso_total_kg REAL"),
        ("ofertas_mercado", "preco_unidade_inicial REAL"),
        ("ofertas_mercado", "tipo_frete_sugerido TEXT"),
        ("ofertas_mercado", "cidade_destino TEXT"),
        ("ofertas_mercado", "estado_destino TEXT"),
        ("ofertas_mercado", "observacoes TEXT"),
    ]
    with engine.connect() as conn:
        for tabela, col in migrations:
            try:
                conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {col}"))
                conn.commit()
            except Exception:
                pass  # coluna já existe


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
