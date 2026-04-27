# Movie Watchlist

Aplicație web full-stack pentru gestionarea unei liste personale de filme.

- **Backend:** FastAPI + SQLite (`sqlite3` din stdlib) + JWT
- **Frontend:** HTML + JavaScript vanilla + Bootstrap 5 (CDN)
- **Deploy:** Render.com (`render.yaml`)

## Funcționalități

- Înregistrare cont utilizator
- Autentificare JWT (OAuth2 Password flow)
- Profil utilizator curent (`/utilizatori/eu`)
- CRUD complet pentru filme
- Marcarea unui film ca văzut
- Filtrare filme după:
  - doar nevăzute
  - gen
- Izolare date per utilizator (`utilizator_id`)

## Structură proiect

```text
movie-watchlist/
├── main.py
├── requirements.txt
├── .env
├── .gitignore
├── render.yaml
└── static/
    └── index.html
```

## Cerințe

- Python 3.10+ (recomandat 3.11/3.12)
- pip

## Instalare locală

```bash
pip install -r requirements.txt
```

Pentru compatibilitate `passlib`, proiectul folosește pin:

- `bcrypt<4.1.0`

## Configurare `.env`

Fișierul `.env` trebuie să conțină:

```env
SECRET_KEY=schimba-cu-o-cheie-random-generata-cu-python-secrets
ALGORITHM=HS256
EXPIRARE_TOKEN_MINUTE=60
DATABASE_PATH=watchlist.db
```

## Pornire aplicație

Portul `8000` poate fi blocat pe unele sisteme Windows. Dacă apare eroare de socket, folosește `8010`.

```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8010
```

Acces:

- App: <http://127.0.0.1:8010>
- Swagger UI: <http://127.0.0.1:8010/docs>
- Health: <http://127.0.0.1:8010/healthz>

## API Endpoint-uri

### Public

- `POST /inregistrare` - creare cont
- `POST /autentificare` - login (returnează `access_token`)
- `GET /healthz` - status aplicație

### Protejate (Bearer Token)

- `GET /utilizatori/eu`
- `GET /filme`
- `GET /filme/{film_id}`
- `POST /filme`
- `PUT /filme/{film_id}`
- `PATCH /filme/{film_id}/vazut`
- `DELETE /filme/{film_id}`

## Exemple rapide (curl)

### 1) Înregistrare

```bash
curl -X POST http://127.0.0.1:8010/inregistrare \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"test@example.com\",\"parola\":\"parola123\"}"
```

### 2) Login

```bash
curl -X POST http://127.0.0.1:8010/autentificare \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=parola123"
```

### 3) Adaugă film (cu token)

```bash
curl -X POST http://127.0.0.1:8010/filme \
  -H "Authorization: Bearer TOKEN_AICI" \
  -H "Content-Type: application/json" \
  -d "{\"titlu\":\"Interstellar\",\"gen\":\"SF\",\"an\":2014,\"descriere\":\"Foarte bun\"}"
```

## Deploy pe Render

`render.yaml` este inclus și configurează:

- build: `pip install -r requirements.txt`
- start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- health check: `/healthz`
- variabile de mediu necesare

Pași:

1. Push proiectul într-un repo Git
2. Creezi un serviciu nou în Render din repo
3. Render detectează `render.yaml` și aplică setările automat

## Troubleshooting

- **[WinError 10013] socket access forbidden**
  - Schimbă portul: `--port 8010` sau `--port 8011`
- **Eroare bcrypt/passlib la înregistrare**
  - Verifică să existe `bcrypt<4.1.0` în `requirements.txt`
  - Reinstalează: `python -m pip install -r requirements.txt`
  - Repornește serverul
- **`/favicon.ico` 404**
  - Este normal dacă nu există favicon în `static/`

## Licență

Utilizare educațională / demo.
