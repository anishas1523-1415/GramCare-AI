import models
from database import SessionLocal, engine
from modules.auth.utils import get_password_hash

models.Base.metadata.create_all(bind=engine)

def seed_db():
    db = SessionLocal()
    
    # Check if P1 exists
    p1 = db.query(models.User).filter(models.User.username == "P1").first()
    if not p1:
        print("Creating Patient P1...")
        patient = models.User(
            username="P1",
            email="patient1@gramcare.ai",
            full_name="Patient One",
            hashed_password=get_password_hash("password123"),
            role="PATIENT"
        )
        db.add(patient)
    
    # Check if D1 exists
    d1 = db.query(models.User).filter(models.User.username == "D1").first()
    if not d1:
        print("Creating Doctor D1...")
        doctor = models.User(
            username="D1",
            email="doctor1@gramcare.ai",
            full_name="Dr. Sarah Jenkins",
            hashed_password=get_password_hash("password123"),
            role="DOCTOR"
        )
        db.add(doctor)
    
    db.commit()
    db.close()
    print("Database seeded successfully!")

if __name__ == "__main__":
    seed_db()
