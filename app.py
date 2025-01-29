from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi.middleware.cors import CORSMiddleware

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"  # Database URL
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database model
class Car(Base):
    __tablename__ = "cars"
    id = Column(Integer, primary_key=True, index=True)
    make = Column(String, index=True)
    model = Column(String, index=True)
    year = Column(Integer)

# Pydantic models (Schemas)
class CarBase(BaseModel):
    make: str
    model: str
    year: int

class CarCreate(CarBase):
    pass

class CarResponse(CarBase):
    id: int

    class Config:
        orm_mode = True

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create database tables
Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CRUD operations

# Create multiple cars
@app.post("/cars", response_model=list[CarResponse])
def create_cars(cars: list[CarCreate], db: Session = Depends(get_db)):
    db_cars = [Car(make=car.make, model=car.model, year=car.year) for car in cars]
    db.add_all(db_cars)
    db.commit()
    for db_car in db_cars:
        db.refresh(db_car)
    return db_cars

# Get all cars
@app.get("/cars", response_model=list[CarResponse])
def get_cars(db: Session = Depends(get_db)):
    cars = db.query(Car).all()
    return cars

# Get a single car by ID
@app.get("/cars/{car_id}", response_model=CarResponse)
def get_car(car_id: int, db: Session = Depends(get_db)):
    db_car = db.query(Car).filter(Car.id == car_id).first()
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    return db_car

# Update a car by ID
@app.put("/cars/{car_id}", response_model=CarResponse)
def update_car(car_id: int, car: CarCreate, db: Session = Depends(get_db)):
    db_car = db.query(Car).filter(Car.id == car_id).first()
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    db_car.make = car.make
    db_car.model = car.model
    db_car.year = car.year
    db.commit()
    db.refresh(db_car)
    return db_car

# Delete a car by ID
@app.delete("/cars/{car_id}", response_model=CarResponse)
def delete_car(car_id: int, db: Session = Depends(get_db)):
    db_car = db.query(Car).filter(Car.id == car_id).first()
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    db.delete(db_car)
    db.commit()
    return db_car
