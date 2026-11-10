"""FastAPI application: users and calculations."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from app.calculations.factory import CalculationError
from app.database import Base, engine, get_db
from app.operations.calculations import (
    UserNotFoundError,
    create_calculation,
    get_calculation,
    list_calculations,
)
from app.operations.users import (
    DuplicateUserError,
    authenticate_user,
    create_user,
    get_user,
)
from app.schemas import CalculationCreate, CalculationRead, UserCreate, UserLogin, UserRead


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Create the tables on startup (no migrations tool in this project yet).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Calculation Model", version="1.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    try:
        return create_user(db, user_in)
    except DuplicateUserError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.get("/users/{user_id}", response_model=UserRead)
def read_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@app.post("/users/verify", response_model=UserRead)
def verify_credentials(credentials: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, credentials.username, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password"
        )
    return user


@app.post("/calculations", response_model=CalculationRead, status_code=status.HTTP_201_CREATED)
def add_calculation(calc_in: CalculationCreate, db: Session = Depends(get_db)):
    try:
        return create_calculation(db, calc_in)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CalculationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@app.get("/calculations", response_model=list[CalculationRead])
def read_calculations(user_id: int | None = None, db: Session = Depends(get_db)):
    return list_calculations(db, user_id)


@app.get("/calculations/{calculation_id}", response_model=CalculationRead)
def read_calculation(calculation_id: int, db: Session = Depends(get_db)):
    calculation = get_calculation(db, calculation_id)
    if calculation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calculation not found")
    return calculation
