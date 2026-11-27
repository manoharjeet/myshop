import os
import shutil
import uuid
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, Session, declarative_base

ADMIN_PASSWORD = "admin123"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

DATABASE_URL = "sqlite:///./products.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)
    image_url = Column(String)

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_admin(x_admin_password: str = Header(None)):
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid Admin Password")

@app.get("/")
def home():
    return FileResponse("index.html")

@app.post("/verify-admin", dependencies=[Depends(verify_admin)])
def check_admin():
    return {"status": "ok"}

@app.get("/products/")
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).order_by(Product.id.desc()).all()

@app.post("/products/", dependencies=[Depends(verify_admin)])
async def create_product(
    name: str = Form(...),
    price: float = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    unique_filename = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image_url = f"/uploads/{unique_filename}"
    new_product = Product(name=name, price=price, image_url=image_url)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

@app.put("/products/{product_id}", dependencies=[Depends(verify_admin)])
async def update_product(
    product_id: int,
    name: str = Form(...),
    price: float = Form(...),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.name = name
    product.price = price

    if file and file.filename:
        old_path = product.image_url.lstrip("/")
        if os.path.exists(old_path):
            os.remove(old_path)

        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
        unique_filename = f"{uuid.uuid4()}.{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        product.image_url = f"/uploads/{unique_filename}"

    db.commit()
    db.refresh(product)
    return product

@app.delete("/products/{product_id}", dependencies=[Depends(verify_admin)])
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        file_path = product.image_url.lstrip("/")
        if os.path.exists(file_path):
            os.remove(file_path)
        db.delete(product)
        db.commit()
    return {"status": "deleted"}
