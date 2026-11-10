"""FastAPI application: calculator page, users and calculations."""

from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.calculations.types import CalculationError
from app.database import get_db
from app.models import Calculation
from app.operations.calculations import (
    UserNotFoundError,
    create_calculation,
    get_calculation,
    list_calculations,
    update_calculation,
)
from app.operations.users import (
    DuplicateUserError,
    authenticate_user,
    create_user,
    get_user,
    get_user_with_calculations,
)
from app.schemas import (
    CalculationBase,
    CalculationCreate,
    CalculationRead,
    CalculationResult,
    CalculationUpdate,
    UserCalculations,
    UserCreate,
    UserLogin,
    UserRead,
)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


# The tables are created and changed by Alembic migrations
# ("alembic upgrade head"), not by the app itself.
app = FastAPI(title="Calculation Model", version="3.0.0")


def calculation_error(exc: CalculationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def calculator_page(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ----- Calculations ------------------------------------------------------


@app.post("/calculate", response_model=CalculationResult)
def calculate(calc_in: CalculationBase):
    """Work out a result without saving it (used by the calculator page)."""
    try:
        calculation = Calculation.create(calc_in.type, calc_in.a, calc_in.b)
    except CalculationError as exc:
        raise calculation_error(exc) from exc
    return CalculationResult(
        a=calculation.a, b=calculation.b, type=calc_in.type, result=calculation.result
    )


@app.post("/calculations", response_model=CalculationRead, status_code=status.HTTP_201_CREATED)
def add_calculation(calc_in: CalculationCreate, db: Session = Depends(get_db)):
    try:
        return create_calculation(db, calc_in)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CalculationError as exc:
        raise calculation_error(exc) from exc


@app.get("/calculations", response_model=list[CalculationRead])
def read_calculations(user_id: UUID | None = None, db: Session = Depends(get_db)):
    return list_calculations(db, user_id)


def find_calculation(calculation_id: UUID, db: Session) -> Calculation:
    calculation = get_calculation(db, calculation_id)
    if calculation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calculation not found")
    return calculation


@app.get("/calculations/{calculation_id}", response_model=CalculationRead)
def read_calculation(calculation_id: UUID, db: Session = Depends(get_db)):
    return find_calculation(calculation_id, db)


@app.patch("/calculations/{calculation_id}", response_model=CalculationRead)
def edit_calculation(
    calculation_id: UUID, changes: CalculationUpdate, db: Session = Depends(get_db)
):
    calculation = find_calculation(calculation_id, db)
    try:
        return update_calculation(db, calculation, changes)
    except CalculationError as exc:
        raise calculation_error(exc) from exc


# ----- Users -------------------------------------------------------------


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    try:
        return create_user(db, user_in)
    except DuplicateUserError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.get("/users/{user_id}", response_model=UserRead)
def read_user(user_id: UUID, db: Session = Depends(get_db)):
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@app.get("/users/{user_id}/calculations", response_model=UserCalculations)
def read_user_calculations(user_id: UUID, db: Session = Depends(get_db)):
    user = get_user_with_calculations(db, user_id)
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
