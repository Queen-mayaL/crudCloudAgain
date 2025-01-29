from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil
import os
import uvicorn

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Image storage directory
IMAGE_DIR = "car_images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Database model
class Car(Base):
    __tablename__ = "cars"
    id = Column(Integer, primary_key=True, index=True)
    make = Column(String, index=True)
    model = Column(String, index=True)
    year = Column(Integer)
    image_filename = Column(String, nullable=True)

# Pydantic models (Schemas)
class CarBase(BaseModel):
    make: str
    model: str
    year: int

class CarCreate(CarBase):
    pass

class CarResponse(CarBase):
    id: int
    image_url: str | None = None

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
    allow_origins=["https://queen-mayal.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded images
app.mount("/car_images", StaticFiles(directory=IMAGE_DIR), name="car_images")

# Create multiple cars
@app.post("/cars", response_model=list[CarResponse])
def create_cars(cars: list[CarCreate], db: Session = Depends(get_db)):
    db_cars = [Car(make=car.make, model=car.model, year=car.year) for car in cars]
    db.add_all(db_cars)
    db.commit()
    for db_car in db_cars:
        db.refresh(db_car)
    return db_cars

# Upload a car image
@app.post("/cars/{car_id}/upload_image")
def upload_car_image(car_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    db_car = db.query(Car).filter(Car.id == car_id).first()
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    
    file_extension = file.filename.split(".")[-1]
    filename = f"car_{car_id}.{file_extension}"
    file_path = os.path.join(IMAGE_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    db_car.image_filename = filename
    db.commit()
    db.refresh(db_car)
    
    return {"image_url": f"/car_images/{filename}"}

# Get all cars
@app.get("/cars", response_model=list[CarResponse])
def get_cars(db: Session = Depends(get_db)):
    cars = db.query(Car).all()
    for car in cars:
        car.image_url = f"/car_images/{car.image_filename}" if car.image_filename else None
    return cars

# Get a single car by ID
@app.get("/cars/{car_id}", response_model=CarResponse)
def get_car(car_id: int, db: Session = Depends(get_db)):
    db_car = db.query(Car).filter(Car.id == car_id).first()
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    db_car.image_url = f"/car_images/{db_car.image_filename}" if db_car.image_filename else None
    return db_car

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
