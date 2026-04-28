import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Generator, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

load_dotenv()

SECRET_KEY: str = os.getenv("SECRET_KEY", "schimba-ma")
ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
EXPIRARE_TOKEN_MINUTE: int = int(os.getenv("EXPIRARE_TOKEN_MINUTE", "60"))
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "watchlist.db")
RESET_DATABASE_ON_START: bool = os.getenv("RESET_DATABASE_ON_START", "false").lower() == "true"

pwd_context: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme: OAuth2PasswordBearer = OAuth2PasswordBearer(tokenUrl="autentificare")


class UtilizatorCreare(BaseModel):
    email: str
    parola: str = Field(min_length=6)


class FilmCreare(BaseModel):
    titlu: str = Field(min_length=1, max_length=200)
    gen: Optional[str] = None
    an: Optional[int] = Field(default=None, ge=1888, le=2100)
    descriere: Optional[str] = None


class FilmActualizare(BaseModel):
    titlu: Optional[str] = Field(default=None, min_length=1, max_length=200)
    gen: Optional[str] = None
    an: Optional[int] = Field(default=None, ge=1888, le=2100)
    descriere: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=10)


def get_db() -> Generator[sqlite3.Connection, None, None]:
    db: sqlite3.Connection = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
    finally:
        db.close()


def initializeaza_db() -> None:
    with sqlite3.connect(DATABASE_PATH) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS utilizatori (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                parola_hash TEXT NOT NULL
            );
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS filme (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titlu TEXT NOT NULL,
                gen TEXT,
                an INTEGER,
                descriere TEXT,
                vazut INTEGER DEFAULT 0,
                rating INTEGER,
                data_adaugarii TEXT NOT NULL,
                utilizator_id INTEGER NOT NULL,
                FOREIGN KEY (utilizator_id) REFERENCES utilizatori(id)
            );
            """
        )
        _populeaza_date_demo(db)
        db.commit()


def _populeaza_date_demo(db: sqlite3.Connection) -> None:
    utilizatori_demo: list[tuple[str, str]] = [
        ("ana@example.com", "parola123"),
        ("mihai@example.com", "parola123"),
        ("ioana@example.com", "parola123"),
    ]
    for email, parola in utilizatori_demo:
        existent: Optional[sqlite3.Row] = db.execute(
            "SELECT id FROM utilizatori WHERE email = ?",
            (email,),
        ).fetchone()
        if existent is None:
            db.execute(
                "INSERT INTO utilizatori (email, parola_hash) VALUES (?, ?)",
                (email, _hash_parola(parola)),
            )

    utilizatori: list[sqlite3.Row] = db.execute(
        "SELECT id, email FROM utilizatori ORDER BY id ASC"
    ).fetchall()
    utilizator_map: dict[str, int] = {row["email"]: row["id"] for row in utilizatori}

    filme_demo: list[tuple[str, str, int, str, int, Optional[int], str, str]] = [
        (
            "Interstellar",
            "SF",
            2014,
            "O călătorie în spațiu și timp pentru salvarea omenirii.",
            1,
            10,
            "2024-01-04T10:00:00",
            "ana@example.com",
        ),
        (
            "Inception",
            "SF",
            2010,
            "Un hoț intră în vise pentru a planta o idee imposibilă.",
            1,
            9,
            "2024-01-10T09:20:00",
            "ana@example.com",
        ),
        (
            "The Dark Knight",
            "Acțiune",
            2008,
            "Batman îl înfruntă pe Joker într-un Gotham haotic.",
            0,
            None,
            "2024-02-01T20:45:00",
            "ana@example.com",
        ),
        (
            "The Hangover",
            "Comedie",
            2009,
            "O noapte nebună în Vegas, urmată de consecințe memorabile.",
            1,
            8,
            "2024-01-15T18:15:00",
            "mihai@example.com",
        ),
        (
            "The Conjuring",
            "Horror",
            2013,
            "Anchetatori paranormali investighează o casă bântuită.",
            0,
            None,
            "2024-03-02T21:30:00",
            "mihai@example.com",
        ),
        (
            "La La Land",
            "Drama",
            2016,
            "Poveste de dragoste între visuri, muzică și compromisuri.",
            1,
            9,
            "2024-02-14T19:00:00",
            "ioana@example.com",
        ),
        (
            "Dune",
            "SF",
            2021,
            "Luptă pentru putere pe planeta deșert Arrakis.",
            0,
            None,
            "2024-03-21T12:00:00",
            "ioana@example.com",
        ),
    ]

    for titlu, gen, an, descriere, vazut, rating, data_adaugarii, email in filme_demo:
        utilizator_id: Optional[int] = utilizator_map.get(email)
        if utilizator_id is None:
            continue

        film_existent: Optional[sqlite3.Row] = db.execute(
            "SELECT id FROM filme WHERE titlu = ? AND utilizator_id = ?",
            (titlu, utilizator_id),
        ).fetchone()
        if film_existent is not None:
            continue

        db.execute(
            """
            INSERT INTO filme (titlu, gen, an, descriere, vazut, rating, data_adaugarii, utilizator_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (titlu, gen, an, descriere, vazut, rating, data_adaugarii, utilizator_id),
        )


def _hash_parola(parola: str) -> str:
    return pwd_context.hash(parola)


def _verifica_parola(parola_text: str, parola_hash: str) -> bool:
    return pwd_context.verify(parola_text, parola_hash)


def _creeaza_access_token(subiect: str) -> str:
    expirare: datetime = datetime.now(timezone.utc) + timedelta(minutes=EXPIRARE_TOKEN_MINUTE)
    payload: dict[str, str] = {"sub": subiect, "exp": expirare}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "titlu": row["titlu"],
        "gen": row["gen"],
        "an": row["an"],
        "descriere": row["descriere"],
        "vazut": bool(row["vazut"]),
        "rating": row["rating"],
        "data_adaugarii": row["data_adaugarii"],
        "utilizator_id": row["utilizator_id"],
    }


def get_utilizator_curent(
    token: str = Depends(oauth2_scheme),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    cred_exception: HTTPException = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalid sau expirat.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: dict = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise cred_exception
    except JWTError as exc:
        raise cred_exception from exc

    utilizator: Optional[sqlite3.Row] = db.execute(
        "SELECT id, email FROM utilizatori WHERE email = ?",
        (email,),
    ).fetchone()
    if utilizator is None:
        raise cred_exception

    return {"id": utilizator["id"], "email": utilizator["email"]}


def _reseteaza_baza_daca_este_cerut() -> None:
    if not RESET_DATABASE_ON_START:
        return

    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _reseteaza_baza_daca_este_cerut()
    initializeaza_db()
    yield


app: FastAPI = FastAPI(title="Movie Watchlist", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/inregistrare")
def inregistrare(utilizator: UtilizatorCreare, db: sqlite3.Connection = Depends(get_db)):
    existent: Optional[sqlite3.Row] = db.execute(
        "SELECT id FROM utilizatori WHERE email = ?",
        (utilizator.email,),
    ).fetchone()
    if existent is not None:
        raise HTTPException(status_code=400, detail="Email-ul există deja.")

    parola_hash: str = _hash_parola(utilizator.parola)
    cursor: sqlite3.Cursor = db.execute(
        "INSERT INTO utilizatori (email, parola_hash) VALUES (?, ?)",
        (utilizator.email, parola_hash),
    )
    db.commit()

    return {"id": cursor.lastrowid, "email": utilizator.email}


@app.post("/autentificare")
def autentificare(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: sqlite3.Connection = Depends(get_db),
):
    utilizator: Optional[sqlite3.Row] = db.execute(
        "SELECT id, email, parola_hash FROM utilizatori WHERE email = ?",
        (form_data.username,),
    ).fetchone()
    if utilizator is None or not _verifica_parola(form_data.password, utilizator["parola_hash"]):
        raise HTTPException(status_code=401, detail="Credențiale invalide.")

    token: str = _creeaza_access_token(utilizator["email"])
    return {"access_token": token, "token_type": "bearer"}


@app.get("/utilizatori/eu")
def utilizator_eu(utilizator_curent: dict = Depends(get_utilizator_curent)):
    return {"id": utilizator_curent["id"], "email": utilizator_curent["email"]}


@app.get("/filme")
def lista_filme(
    doar_nevazute: bool = False,
    gen: Optional[str] = None,
    utilizator_curent: dict = Depends(get_utilizator_curent),
    db: sqlite3.Connection = Depends(get_db),
):
    query: str = """
        SELECT id, titlu, gen, an, descriere, vazut, rating, data_adaugarii, utilizator_id
        FROM filme
        WHERE utilizator_id = ?
    """
    params: list = [utilizator_curent["id"]]
    if doar_nevazute:
        query += " AND vazut = 0"
    if gen is not None and gen.strip() != "":
        query += " AND gen = ?"
        params.append(gen.strip())
    query += " ORDER BY data_adaugarii DESC"

    rows: list[sqlite3.Row] = db.execute(query, tuple(params)).fetchall()
    return [_row_to_dict(row) for row in rows]


@app.get("/filme/{film_id}")
def film_dupa_id(
    film_id: int,
    utilizator_curent: dict = Depends(get_utilizator_curent),
    db: sqlite3.Connection = Depends(get_db),
):
    film: Optional[sqlite3.Row] = db.execute(
        """
        SELECT id, titlu, gen, an, descriere, vazut, rating, data_adaugarii, utilizator_id
        FROM filme
        WHERE id = ? AND utilizator_id = ?
        """,
        (film_id, utilizator_curent["id"]),
    ).fetchone()
    if film is None:
        raise HTTPException(status_code=404, detail="Filmul nu a fost găsit.")

    return _row_to_dict(film)


@app.post("/filme", status_code=201)
def adauga_film(
    film: FilmCreare,
    utilizator_curent: dict = Depends(get_utilizator_curent),
    db: sqlite3.Connection = Depends(get_db),
):
    data_adaugarii: str = datetime.now().isoformat()
    cursor: sqlite3.Cursor = db.execute(
        """
        INSERT INTO filme (titlu, gen, an, descriere, vazut, rating, data_adaugarii, utilizator_id)
        VALUES (?, ?, ?, ?, 0, NULL, ?, ?)
        """,
        (
            film.titlu,
            film.gen,
            film.an,
            film.descriere,
            data_adaugarii,
            utilizator_curent["id"],
        ),
    )
    db.commit()

    film_nou: Optional[sqlite3.Row] = db.execute(
        """
        SELECT id, titlu, gen, an, descriere, vazut, rating, data_adaugarii, utilizator_id
        FROM filme
        WHERE id = ? AND utilizator_id = ?
        """,
        (cursor.lastrowid, utilizator_curent["id"]),
    ).fetchone()
    return _row_to_dict(film_nou)


@app.put("/filme/{film_id}")
def actualizeaza_film(
    film_id: int,
    payload: FilmActualizare,
    utilizator_curent: dict = Depends(get_utilizator_curent),
    db: sqlite3.Connection = Depends(get_db),
):
    existent: Optional[sqlite3.Row] = db.execute(
        "SELECT id FROM filme WHERE id = ? AND utilizator_id = ?",
        (film_id, utilizator_curent["id"]),
    ).fetchone()
    if existent is None:
        raise HTTPException(status_code=404, detail="Filmul nu a fost găsit.")

    update_data: dict = payload.model_dump(exclude_unset=True)
    if len(update_data) == 0:
        film: Optional[sqlite3.Row] = db.execute(
            """
            SELECT id, titlu, gen, an, descriere, vazut, rating, data_adaugarii, utilizator_id
            FROM filme
            WHERE id = ? AND utilizator_id = ?
            """,
            (film_id, utilizator_curent["id"]),
        ).fetchone()
        return _row_to_dict(film)

    set_fragments: list[str] = []
    values: list = []
    for key, value in update_data.items():
        set_fragments.append(f"{key} = ?")
        values.append(value)
    values.extend([film_id, utilizator_curent["id"]])

    query: str = f"UPDATE filme SET {', '.join(set_fragments)} WHERE id = ? AND utilizator_id = ?"
    db.execute(query, tuple(values))
    db.commit()

    actualizat: Optional[sqlite3.Row] = db.execute(
        """
        SELECT id, titlu, gen, an, descriere, vazut, rating, data_adaugarii, utilizator_id
        FROM filme
        WHERE id = ? AND utilizator_id = ?
        """,
        (film_id, utilizator_curent["id"]),
    ).fetchone()
    return _row_to_dict(actualizat)


@app.patch("/filme/{film_id}/vazut")
def marcheaza_ca_vazut(
    film_id: int,
    utilizator_curent: dict = Depends(get_utilizator_curent),
    db: sqlite3.Connection = Depends(get_db),
):
    rezultat: sqlite3.Cursor = db.execute(
        "UPDATE filme SET vazut = 1 WHERE id = ? AND utilizator_id = ?",
        (film_id, utilizator_curent["id"]),
    )
    if rezultat.rowcount == 0:
        raise HTTPException(status_code=404, detail="Filmul nu a fost găsit.")
    db.commit()

    actualizat: Optional[sqlite3.Row] = db.execute(
        """
        SELECT id, titlu, gen, an, descriere, vazut, rating, data_adaugarii, utilizator_id
        FROM filme
        WHERE id = ? AND utilizator_id = ?
        """,
        (film_id, utilizator_curent["id"]),
    ).fetchone()
    return _row_to_dict(actualizat)


@app.delete("/filme/{film_id}")
def sterge_film(
    film_id: int,
    utilizator_curent: dict = Depends(get_utilizator_curent),
    db: sqlite3.Connection = Depends(get_db),
):
    rezultat: sqlite3.Cursor = db.execute(
        "DELETE FROM filme WHERE id = ? AND utilizator_id = ?",
        (film_id, utilizator_curent["id"]),
    )
    if rezultat.rowcount == 0:
        raise HTTPException(status_code=404, detail="Filmul nu a fost găsit.")
    db.commit()

    return {"mesaj": "Filmul a fost șters cu succes."}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
