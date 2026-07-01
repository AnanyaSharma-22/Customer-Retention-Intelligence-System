from app.db.base import Base
from app.db.database import engine

# Import all models
from app.db.dataset import Dataset
from app.db.customer import Customer
from app.db.prediction import Prediction
from app.db.prediction_history import PredictionHistory
from app.db.upload_job import UploadJob
from app.db.customer_feature import CustomerFeature

def create_tables():
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created successfully!")


if __name__ == "__main__":
    create_tables()