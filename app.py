from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil
import os
import uvicorn
from typing import Optional
import json
from dotenv import load_dotenv
from fastapi.responses import FileResponse
load_dotenv()

# Database setup
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment variables")
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"sslmode": "require"})
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
    image_url: Optional[str] = None

    class Config:
        from_attributes = True

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

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")

@app.post("/cars", response_model=list[CarResponse])
def create_cars(
    cars: str = Form(...),  # Accept JSON as a string
    files: list[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    from pydantic import parse_obj_as
    
    try:
        cars_data = parse_obj_as(list[CarCreate], json.loads(cars))  # Convert JSON string to list
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON format")

    if files and len(files) != len(cars_data):
        raise HTTPException(status_code=400, detail="Number of images must match number of cars")

    db_cars = []
    for i, car in enumerate(cars_data):
        db_car = Car(make=car.make, model=car.model, year=car.year)
        db.add(db_car)
        db.commit()
        db.refresh(db_car)

        if files and files[i]:
            file = files[i]
            file_extension = file.filename.split(".")[-1]
            filename = f"car_{db_car.id}.{file_extension}"
            file_path = os.path.join(IMAGE_DIR, filename)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            db_car.image_filename = filename
            db.commit()
            db.refresh(db_car)

        db_cars.append(db_car)

    return db_cars

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

@app.delete("/cars/{car_id}")
def delete_car(car_id: int, db: Session = Depends(get_db)):
    db_car = db.query(Car).filter(Car.id == car_id).first()
    if not db_car:
        raise HTTPException(status_code=404, detail="Car not found")

    # Delete car image if exists
    if db_car.image_filename:
        file_path = os.path.join(IMAGE_DIR, db_car.image_filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.delete(db_car)
    db.commit()
    return {"message": "Car deleted successfully"}

@app.put("/cars/{car_id}")
def update_car(
    car_id: int,
    make: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    db_car = db.query(Car).filter(Car.id == car_id).first()
    if not db_car:
        raise HTTPException(status_code=404, detail="Car not found")

    # Only update fields that are provided
    if make:
        db_car.make = make
    if model:
        db_car.model = model
    if year:
        try:
            db_car.year = int(year)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid year format")

    # Handle image upload
    if file:
        file_extension = file.filename.split(".")[-1]
        filename = f"car_{db_car.id}.{file_extension}"
        file_path = os.path.join(IMAGE_DIR, filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        db_car.image_filename = filename

    db.commit()
    db.refresh(db_car)

    return db_car

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
