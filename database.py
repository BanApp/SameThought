from sqlalchemy import create_engine, Column, String, Date, Enum, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "mysql+pymysql://root:jmj1079132@localhost/userinfo"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=True)
    birth_date = Column(Date, nullable=True)
    gender = Column(Enum('M', 'F', 'U'), nullable=True)  # U for unspecified


Base.metadata.create_all(bind=engine)
