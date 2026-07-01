from pathlib import Path
import shutil

from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.services.feature_service import (
    save_customer_features,
)
from app.db.dataset import Dataset
from app.dependencies import get_current_user, get_db
from app.services.preprocessing_service import (
    load_uploaded_file,
    get_uploaded_columns,
)
from app.services.prediction_service import (
    predict_dataset,
    save_customers,
    save_predictions,
)
from app.services.mapping_service import (
    validate_mapping,
    apply_mapping,
)
router = APIRouter(
    prefix="/upload",
    tags=["Dataset Upload"],
)


@router.post("/")
async def upload_dataset(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validate file extension
    allowed_extensions = [".csv", ".xlsx", ".xls"]

    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail="Only CSV and Excel files are allowed.",
        )

    # Create user storage folder
    user_folder = Path("storage") / current_user.id
    user_folder.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    file_path = user_folder / file.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Load dataset
    df = load_uploaded_file(str(file_path))
    uploaded_columns = get_uploaded_columns(df)

    # Validate required columns
    

    total_rows = len(df)

    # Create dataset record
    dataset = Dataset(
        user_id=current_user.id,
        name=file.filename.rsplit(".", 1)[0],
        file_name=file.filename,
        total_rows=total_rows,
        status="uploaded",
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return {
        "message": "File uploaded successfully.",
        "dataset_id": str(dataset.id),
        "filename": file.filename,
        "content_type": file.content_type,
        "saved_path": str(file_path),
        "uploaded_by": current_user.email,
        "status": dataset.status,
        "total_rows": dataset.total_rows,
        "columns": uploaded_columns,
    }

class MappingRequest(BaseModel):
    dataset_id: str
    mapping: dict[str, str]

@router.post("/map-columns")
async def map_columns(
    request: MappingRequest,
    db: Session = Depends(get_db),
):
    try:
        validate_mapping(request.mapping)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == request.dataset_id)
        .first()
    )

    if not dataset:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    file_path = (
        Path("storage")
        / dataset.user_id
        / dataset.file_name
    )

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Uploaded file not found.",
        )

    df = load_uploaded_file(str(file_path))

    df = apply_mapping(
        df,
        request.mapping,
    )

    dataset.mapping_completed = True

    db.commit()
    db.refresh(dataset)

    return {
    "message": "Column mapping completed successfully.",
    "dataset_id": str(dataset.id),
    "mapping_completed": dataset.mapping_completed,
    "mapped_columns": df.columns.tolist(),
}

@router.post("/predict/{dataset_id}")
async def predict_dataset_api(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id)
        .first()
    )

    if not dataset:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )
    if not dataset.mapping_completed:
        raise HTTPException(
        status_code=400,
        detail="Please complete column mapping first.",
    )
    if dataset.status == "predicted":
     return {
        "message": "Predictions already exist for this dataset.",
        "dataset_id": str(dataset.id),
    }

    file_path = (
        Path("storage")
        / dataset.user_id
        / dataset.file_name
    )

    if not file_path.exists():
       raise HTTPException(
        status_code=404,
        detail="Dataset file not found.",
    )

    prediction_df, feature_names = predict_dataset(
    str(file_path)
    )

    customers = save_customers(
        db=db,
        dataset_id=dataset.id,
        prediction_df=prediction_df,
    )

    save_customer_features(
    db=db,
    customers=customers,
    prediction_df=prediction_df,
    feature_names=feature_names,
    )

    predictions = save_predictions(
        db=db,
        customers=customers,
        prediction_df=prediction_df,
    )

    dataset.status = "predicted"
    db.commit()

    return {
        "message": "Prediction completed successfully.",
        "customers_processed": len(customers),
        "predictions_saved": len(predictions),
    }