from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
import models
from database import get_db

router = APIRouter()

class Medicine(BaseModel):
    id: int
    name: str
    stock_quantity: int
    minimum_threshold: int = 50
    status: str = "Optimal"
    
    model_config = {"from_attributes": True}

@router.get("/stock", response_model=List[Medicine])
async def get_inventory_status(db: Session = Depends(get_db)):
    """
    Called by the Pharmacy Web Dashboard.
    Returns current stock levels and alerts for shortages from SQLite DB.
    """
    items = db.query(models.PharmacyItem).all()
    
    # If DB is empty, seed it with mock data
    if not items:
        seed_data = [
            models.PharmacyItem(pharmacy_id="P1", medicine_name="Paracetamol 500mg", stock_count=45),
            models.PharmacyItem(pharmacy_id="P1", medicine_name="Amoxicillin 250mg", stock_count=120),
            models.PharmacyItem(pharmacy_id="P1", medicine_name="Insulin Glargine", stock_count=0)
        ]
        db.add_all(seed_data)
        db.commit()
        items = db.query(models.PharmacyItem).all()
    
    response = []
    for item in items:
        status = "Optimal"
        if item.stock_count == 0:
            status = "Out of Stock"
        elif item.stock_count < 50:
            status = "Low"
            
        response.append({
            "id": item.id,
            "name": item.medicine_name,
            "stock_quantity": item.stock_count,
            "minimum_threshold": 50,
            "status": status
        })
        
    return response

@router.post("/update_stock/{medicine_id}")
async def update_stock(medicine_id: int, quantity_added: int, db: Session = Depends(get_db)):
    """
    Called when a new shipment arrives.
    """
    item = db.query(models.PharmacyItem).filter(models.PharmacyItem.id == medicine_id).first()
    if not item:
        return {"error": "Medicine not found"}
        
    item.stock_count += quantity_added
    db.commit()
    db.refresh(item)
    
    return {"message": f"Stock updated successfully. New quantity: {item.stock_count}", "id": item.id}
