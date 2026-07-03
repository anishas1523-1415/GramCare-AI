"""Pharmacy network — inventory lifecycle, geo search, substitutes, expiry.

Planning-doc features implemented here:
- Pharmacist registers their shop with a location; patients search nearby
  pharmacies for a medicine and see green/red availability
  ("பக்கத்துல இருக்கற எந்த பார்மசியில அந்த மருந்து இருக்குன்னு காட்டும்").
- Rural-friendly stock entry: absolute count ("டேக்கு கடைசியில எவ்வளவு
  மாத்திரைகள் இருக்குன்னு ஒரு கவுண்ட்டை மேனுவலா என்டர் பண்ணலாம்") and
  tap-to-decrement ("விற்பனை செஞ்ச எண்ணிக்கையை அப்போதைக்கு அப்போ ஒரு தட்டு
  தட்டி பதிவு செஞ்சிடலாம்"), plus the existing shipment delta.
- Generic substitutes via generic_group; expiry alerts (orange list).
- Fulfilling a prescription decrements stock atomically and records which
  pharmacy fulfilled it.
"""
import math
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import get_current_user, require_role

router = APIRouter()


# ==========================================================
# Helpers
# ==========================================================

def _my_pharmacy(user: models.User, db: Session) -> models.Pharmacy:
    pharmacy = (
        db.query(models.Pharmacy)
        .filter(models.Pharmacy.owner_user_id == user.id)
        .first()
    )
    if not pharmacy:
        raise HTTPException(
            status_code=409,
            detail="No pharmacy registered for this account yet. POST /pharmacy/register first.",
        )
    return pharmacy


def _status_for(stock_count: int) -> str:
    """Single source of truth for stock-status labels (shared with the
    dashboard via the API response)."""
    if stock_count <= 0:
        return "Out of Stock"
    if stock_count < 50:
        return "Low"
    return "Optimal"


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _item_response(item: models.PharmacyItem) -> dict:
    return {
        "id": item.id,
        "pharmacy_id": item.pharmacy_id,
        "medicine_name": item.medicine_name,
        "generic_group": item.generic_group,
        "stock_count": item.stock_count,
        "price": item.price,
        "requires_prescription": item.requires_prescription,
        "expiry_date": item.expiry_date,
        "batch_number": item.batch_number,
        "status": _status_for(item.stock_count),
    }


# ==========================================================
# Pharmacy registration / profile
# ==========================================================

@router.post("/register", response_model=schemas.PharmacyResponse)
async def register_pharmacy(
    body: schemas.PharmacyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PHARMACIST")),
):
    """Create or update the caller's pharmacy profile (one per account)."""
    pharmacy = (
        db.query(models.Pharmacy)
        .filter(models.Pharmacy.owner_user_id == current_user.id)
        .first()
    )
    if pharmacy:
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(pharmacy, field, value)
    else:
        pharmacy = models.Pharmacy(owner_user_id=current_user.id, **body.model_dump())
        db.add(pharmacy)
    db.commit()
    db.refresh(pharmacy)
    return pharmacy


@router.get("/me", response_model=schemas.PharmacyResponse)
async def my_pharmacy(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PHARMACIST")),
):
    return _my_pharmacy(current_user, db)


# ==========================================================
# Inventory lifecycle (pharmacist)
# ==========================================================

@router.get("/stock")
async def get_inventory_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PHARMACIST")),
):
    """The caller's OWN inventory. Previously this returned every row in the
    system to any authenticated user; inventory is now scoped per pharmacy.
    Patients use GET /pharmacy/search instead."""
    pharmacy = _my_pharmacy(current_user, db)
    items = (
        db.query(models.PharmacyItem)
        .filter(models.PharmacyItem.pharmacy_id == pharmacy.id)
        .order_by(models.PharmacyItem.medicine_name)
        .all()
    )
    return [_item_response(i) for i in items]


@router.post("/items", status_code=201)
async def add_item(
    body: schemas.PharmacyItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PHARMACIST")),
):
    """Add a medicine to the caller's inventory (used directly and by the
    invoice-OCR entry flow in the dashboard)."""
    pharmacy = _my_pharmacy(current_user, db)
    existing = (
        db.query(models.PharmacyItem)
        .filter(
            models.PharmacyItem.pharmacy_id == pharmacy.id,
            func.lower(models.PharmacyItem.medicine_name) == body.medicine_name.lower(),
        )
        .first()
    )
    if existing:
        # Same medicine again = a restock, not a duplicate row.
        existing.stock_count += body.stock_count
        if body.price:
            existing.price = body.price
        if body.expiry_date:
            existing.expiry_date = body.expiry_date
        if body.batch_number:
            existing.batch_number = body.batch_number
        if body.generic_group:
            existing.generic_group = body.generic_group
        db.commit()
        db.refresh(existing)
        return _item_response(existing)

    item = models.PharmacyItem(pharmacy_id=pharmacy.id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_response(item)


def _owned_item(medicine_id: int, user: models.User, db: Session) -> models.PharmacyItem:
    pharmacy = _my_pharmacy(user, db)
    item = (
        db.query(models.PharmacyItem)
        .filter(
            models.PharmacyItem.id == medicine_id,
            models.PharmacyItem.pharmacy_id == pharmacy.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Medicine not found in your inventory")
    return item


@router.post("/update_stock/{medicine_id}")
async def update_stock(
    medicine_id: int,
    quantity_added: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PHARMACIST")),
):
    """Shipment delta (positive) or correction (negative)."""
    if quantity_added == 0:
        raise HTTPException(status_code=400, detail="quantity_added must be non-zero")
    item = _owned_item(medicine_id, current_user, db)
    new_count = item.stock_count + quantity_added
    if new_count < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reduce stock below zero (current: {item.stock_count}, requested change: {quantity_added})",
        )
    item.stock_count = new_count
    db.commit()
    db.refresh(item)
    return {"message": f"Stock updated successfully. New quantity: {item.stock_count}", "id": item.id}


@router.post("/set_stock/{medicine_id}")
async def set_stock(
    medicine_id: int,
    count: int = Query(..., ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PHARMACIST")),
):
    """Absolute end-of-day count — the planning doc's rural entry mode for
    shops without billing systems."""
    item = _owned_item(medicine_id, current_user, db)
    item.stock_count = count
    db.commit()
    return {"message": f"Stock set to {count}", "id": item.id}


@router.post("/decrement/{medicine_id}")
async def decrement_stock(
    medicine_id: int,
    count: int = Query(1, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PHARMACIST")),
):
    """Tap-to-decrement on sale — the planning doc's other rural entry mode."""
    item = _owned_item(medicine_id, current_user, db)
    item.stock_count = max(0, item.stock_count - count)
    db.commit()
    return {"message": f"Sold {count}. Remaining: {item.stock_count}", "id": item.id}


@router.get("/expiring")
async def expiring_items(
    days: int = Query(90, ge=1, le=730),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PHARMACIST")),
):
    """Medicines expiring within `days` — backs the orange-coded Expiry
    Alerts tab from the planning discussion."""
    pharmacy = _my_pharmacy(current_user, db)
    cutoff = date.today() + timedelta(days=days)
    items = (
        db.query(models.PharmacyItem)
        .filter(
            models.PharmacyItem.pharmacy_id == pharmacy.id,
            models.PharmacyItem.expiry_date != None,  # noqa: E711
            models.PharmacyItem.expiry_date <= cutoff,
            models.PharmacyItem.stock_count > 0,
        )
        .order_by(models.PharmacyItem.expiry_date)
        .all()
    )
    return [
        {**_item_response(i), "days_left": (i.expiry_date - date.today()).days}
        for i in items
    ]


# ==========================================================
# Prescription fulfillment queue
# ==========================================================

@router.get("/queue", response_model=List[schemas.PrescriptionResponse])
async def get_prescription_queue(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PHARMACIST")),
):
    """Unfulfilled digital prescriptions awaiting pickup, newest first."""
    return (
        db.query(models.Prescription)
        .filter(models.Prescription.is_fulfilled == False)  # noqa: E712
        .order_by(models.Prescription.created_at.desc())
        .limit(100)
        .all()
    )


@router.put("/fulfill/{prescription_id}")
async def fulfill_prescription(
    prescription_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PHARMACIST")),
):
    """Mark a prescription fulfilled AND decrement the fulfilling pharmacy's
    stock (previously fulfillment never touched inventory, so counts
    silently drifted from reality — audit item H7).

    Assumption (documented): one pack/unit is decremented per prescribed
    medicine, since prescriptions carry frequency/duration rather than a
    dispensed-units field. Pharmacists can correct counts via set_stock.
    """
    pharmacy = _my_pharmacy(current_user, db)
    prescription = (
        db.query(models.Prescription)
        .filter(models.Prescription.id == prescription_id)
        .first()
    )
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    if prescription.is_fulfilled:
        raise HTTPException(status_code=400, detail="Prescription already fulfilled")

    decremented, missing = [], []
    for med in (prescription.medicines or []):
        name = (med.get("name") or "").strip()
        if not name:
            continue
        item = (
            db.query(models.PharmacyItem)
            .filter(
                models.PharmacyItem.pharmacy_id == pharmacy.id,
                func.lower(models.PharmacyItem.medicine_name) == name.lower(),
            )
            .first()
        )
        if item and item.stock_count > 0:
            item.stock_count -= 1
            decremented.append(name)
        else:
            missing.append(name)

    prescription.is_fulfilled = True
    prescription.fulfilled_by_pharmacy_id = pharmacy.id
    db.commit()

    return {
        "message": "Prescription marked as fulfilled",
        "id": prescription.id,
        "stock_decremented": decremented,
        "not_in_your_stock": missing,
    }


# ==========================================================
# Patient-facing search (nearby availability + substitutes)
# ==========================================================

@router.get("/substitutes")
async def generic_substitutes(
    medicine: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Cheaper/equivalent alternatives in the same generic group, anywhere
    in the network with stock ("விலை அதிகமான மருந்துகளுக்கு பதிலா அதே வேலை
    செய்யும் குறைந்த விலை மருந்துகள்")."""
    source = (
        db.query(models.PharmacyItem)
        .filter(func.lower(models.PharmacyItem.medicine_name) == medicine.lower())
        .filter(models.PharmacyItem.generic_group != None)  # noqa: E711
        .first()
    )
    if not source:
        return []
    subs = (
        db.query(models.PharmacyItem)
        .filter(
            models.PharmacyItem.generic_group == source.generic_group,
            func.lower(models.PharmacyItem.medicine_name) != medicine.lower(),
            models.PharmacyItem.stock_count > 0,
        )
        .all()
    )
    # Deduplicate by name, cheapest first
    by_name: dict = {}
    for s in subs:
        if s.medicine_name not in by_name or s.price < by_name[s.medicine_name]["price"]:
            by_name[s.medicine_name] = {"name": s.medicine_name, "price": s.price}
    return sorted(by_name.values(), key=lambda x: x["price"])


@router.get("/search", response_model=List[schemas.NearbyPharmacyResult])
async def search_medicine(
    medicine: str = Query(..., min_length=2),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(25.0, gt=0, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Nearby-pharmacy availability for a medicine (green/red per the
    planning doc). Location is optional — without it, all active pharmacies
    are returned undistanced (rural users may not grant GPS).

    Distance math note: SQLite has no trig functions, so candidates are
    coarse-filtered with a bounding box in SQL and exact Haversine distances
    are computed in Python — fine at pilot scale (hundreds of pharmacies).
    """
    q = db.query(models.Pharmacy).filter(models.Pharmacy.is_active == True)  # noqa: E712
    if lat is not None and lng is not None:
        # ~1 deg latitude = 111 km; longitude scaled by cos(lat)
        dlat = radius_km / 111.0
        dlng = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))
        q = q.filter(
            models.Pharmacy.lat.between(lat - dlat, lat + dlat),
            models.Pharmacy.lng.between(lng - dlng, lng + dlng),
        )
    pharmacies = q.limit(200).all()

    results: List[schemas.NearbyPharmacyResult] = []
    for pharmacy in pharmacies:
        distance = None
        if lat is not None and lng is not None and pharmacy.lat is not None and pharmacy.lng is not None:
            distance = round(_haversine_km(lat, lng, pharmacy.lat, pharmacy.lng), 1)
            if distance > radius_km:
                continue

        item = (
            db.query(models.PharmacyItem)
            .filter(
                models.PharmacyItem.pharmacy_id == pharmacy.id,
                func.lower(models.PharmacyItem.medicine_name).contains(medicine.lower()),
            )
            .order_by(models.PharmacyItem.stock_count.desc())
            .first()
        )
        available = bool(item and item.stock_count > 0)

        substitutes: List[str] = []
        if not available:
            # Suggest in-stock generic equivalents AT THIS pharmacy
            group_source = (
                db.query(models.PharmacyItem.generic_group)
                .filter(func.lower(models.PharmacyItem.medicine_name).contains(medicine.lower()))
                .filter(models.PharmacyItem.generic_group != None)  # noqa: E711
                .first()
            )
            if group_source and group_source[0]:
                subs = (
                    db.query(models.PharmacyItem)
                    .filter(
                        models.PharmacyItem.pharmacy_id == pharmacy.id,
                        models.PharmacyItem.generic_group == group_source[0],
                        models.PharmacyItem.stock_count > 0,
                    )
                    .limit(5)
                    .all()
                )
                substitutes = [s.medicine_name for s in subs]

        results.append(schemas.NearbyPharmacyResult(
            pharmacy_id=pharmacy.id,
            pharmacy_name=pharmacy.name,
            address=pharmacy.address,
            phone=pharmacy.phone,
            distance_km=distance,
            available=available,
            medicine_name=item.medicine_name if item else None,
            price=item.price if (item and available) else None,
            substitutes=substitutes,
        ))

    # Available first, then nearest
    results.sort(key=lambda r: (not r.available, r.distance_km if r.distance_km is not None else 1e9))
    return results
