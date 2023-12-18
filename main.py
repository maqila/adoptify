import pandas as pd
import sqlalchemy
import hashlib
import os

from fastapi import FastAPI, Depends, HTTPException
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from db import connect_unix_socket, connect_tcp_socket
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from pathlib import Path
# Import kebutuhan Login
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

# Load environment variables
dotenv_path = Path("./.env")
load_dotenv(dotenv_path=dotenv_path)

# Define models for register
    
def generate_password_hash(password):
    hashed_password = pwd_context.hash(password.encode())
    return hashed_password

SECRET_KEY = "maqila"  # Ganti dengan kunci rahasia yang kuat
# Konfigurasi JWT
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Initialize FastAPI app
app = FastAPI()

# Konfigurasi otentikasi
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Konfigurasi password hashing
pwd_context = CryptContext(schemes=["bcrypt", "sha256_crypt"], deprecated="auto")

# Fungsi bantuan untuk membuat token
def create_access_token(data: dict, expires_delta: timedelta or None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Fungsi bantuan untuk mendapatkan user dari database berdasarkan username
def get_user(db_session, email: str):
    with db_session.connect() as conn:
        try:
            existing_user = conn.execute(
                sqlalchemy.text(f'SELECT * FROM "user" WHERE "email" = \'{email}\';')
            ).fetchone()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error: {e}")

    return existing_user[3]

# Fungsi bantuan untuk memverifikasi kata sandi
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Fungsi bantuan untuk mendapatkan sesi database
def get_db():
    db = connect_unix_socket()
    # db = connect_tcp_socket()
    try:
        yield db
    finally:
        db.close()

# Login API
@app.post("/api/login")
async def login_for_access_token(
    email: str,password: str, db: Session = Depends(connect_unix_socket) #connect_tcp_socket
):
    hashedPassUser = get_user(db, email)
    if not email or not verify_password(password, hashedPassUser):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

# Register API
@app.post("/api/register")
async def register(username: str,email: str,password:str, db: Session = Depends(connect_unix_socket)): #connect_tcp_socket
    # Check if username and email are provided
    if not username or not email:
        raise HTTPException(status_code=400, detail="Missing username or email")

    # Check if email is already registered
    with db.connect() as conn:
        try:
            existing_user = conn.execute(
                sqlalchemy.text(f'SELECT * FROM "user" WHERE "email" = \'{email}\';')
            ).fetchone()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error: {e}")

        if existing_user:
            raise HTTPException(status_code=409, detail="Email already registered")

    # Hash password

    hashed_password = generate_password_hash(password)

    # Insert user data
    with db.connect() as conn:
        try:
            conn.execute(
                sqlalchemy.text(
                    f'INSERT INTO "user" (username, email, password) VALUES '
                    f"('{username}', '{email}', '{hashed_password}')"
                )
            )
            conn.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error: {e}")

    return {
        "status": 201,
        "msg": "Successfully registered",
        "data": {
            "username": username,
            "email": email,
        },
    }

#API Pet-recommendation
@app.get("/api/pet-recommendations")
async def pet_recommendations(petId: int, recomType: str):
    db = connect_unix_socket()
    # db = connect_tcp_socket()
    with db.connect() as conn:
        data = pd.read_sql(
            sqlalchemy.text(
                "SELECT * FROM tbAdoptify"
            ),
            conn
        )
    print(data.keys())
    
    data["kontak"] = data["kontak"].str.replace("'", "")
    # data.rename(columns={"ID": "UID"}, inplace=True)
    # RAS

    tf = TfidfVectorizer()
    tf.fit(data["ras"])
    # tf.get_feature_names_out()

    tfidf_matrix_ras = tf.fit_transform(data["ras"])


    cosine_sim_ras = cosine_similarity(tfidf_matrix_ras)
    #     cosine_sim_ras

    cosine_sim_df_ras = pd.DataFrame(
        cosine_sim_ras, index=data["uid"], columns=data["uid"]
    )
    print(cosine_sim_df_ras)


    def ras_hewan_recommendations(
        UID, similarity_data=cosine_sim_df_ras, items=data, k=5
    ):
        index = similarity_data.loc[:, UID].to_numpy().argpartition(range(-1, -k, -1))
        closest = similarity_data.columns[index[-1 : -(k + 2) : -1]]
        closest = closest.drop(UID, errors="ignore")
        return pd.DataFrame(closest).merge(items).head(k)

    # Kesehatan
    tf = TfidfVectorizer()
    tf.fit(data["kesehatan"])


    tfidf_matrix_kesehatan = tf.fit_transform(data["kesehatan"])


    cosine_sim_kesehatan = cosine_similarity(tfidf_matrix_kesehatan)
    cosine_sim_df_kesehatan = pd.DataFrame(
        cosine_sim_kesehatan, index=data["uid"], columns=data["uid"]
    )


    def kesehatan_hewan_recommendations(
        UID,
        similarity_data=cosine_sim_df_kesehatan,
        items=data,
        k=5,
    ):
        index = similarity_data.loc[:, UID].to_numpy().argpartition(range(-1, -k, -1))
        closest = similarity_data.columns[index[-1 : -(k + 2) : -1]]
        closest = closest.drop(UID, errors="ignore")
        return pd.DataFrame(closest).merge(items).head(k)


    # JENIS
    tf = TfidfVectorizer()
    tf.fit(data["jenis"])
    tf.get_feature_names_out()

    tfidf_matrix_jenis = tf.fit_transform(data["jenis"])


    cosine_sim_jenis = cosine_similarity(tfidf_matrix_jenis)
    cosine_sim_df_jenis = pd.DataFrame(
        cosine_sim_jenis, index=data["uid"], columns=data["uid"]
    )

    def jenis_hewan_recommendations(
        UID, similarity_data=cosine_sim_df_jenis, items=data, k=5
    ):
        index = similarity_data.loc[:, UID].to_numpy().argpartition(range(-1, -k, -1))
        closest = similarity_data.columns[index[-1 : -(k + 2) : -1]]
        closest = closest.drop(UID, errors="ignore")
        return pd.DataFrame(closest).merge(items).head(k)

    # MEAN RAS KESEHATAN
    mean_data = (cosine_sim_df_kesehatan + cosine_sim_df_ras) / 2

    def mean_kesehatan_ras_recommendation(
        UID, similarity_data=mean_data, items=data, k=10
    ):
        index = similarity_data.loc[:, UID].to_numpy().argpartition(range(-1, -k, -1))
        closest = similarity_data.columns[index[-1 : -(k + 2) : -1]]
        closest = closest.drop(UID, errors="ignore")
        return pd.DataFrame(closest).merge(items).head(k)
    
    df_result = pd.DataFrame()

    if recomType.lower() == "all":
        df_result = mean_kesehatan_ras_recommendation(petId)
    if recomType.lower() == "ras":
        df_result = ras_hewan_recommendations(petId)
    if recomType.lower() == "kesehatan":
        df_result = kesehatan_hewan_recommendations(petId)
    if recomType.lower() == "jenis":
        df_result = jenis_hewan_recommendations(petId)
        

    return {
        "status": 200,
        "msg": "Success Generate Recommendations",
        "data": df_result.to_dict("records"),
    }
    
#API list pet
@app.get("/api/pet")
async def pet():
    db = connect_unix_socket()
    # db = connect_tcp_socket()
    with db.connect() as conn:
        data = pd.read_sql(
            sqlalchemy.text(
                f"SELECT * FROM tbAdoptify"
            ),
            conn
        )
    return {
        "status": 200,
        "msg": "Success Generate Recommendations",
        "data": data.to_dict('records'),
    }
    
#API detail pet
@app.get("/api/pet-detail")
async def pet_detail(petId: int):
    db = connect_unix_socket()
    # db = connect_tcp_socket()
    with db.connect() as conn:
        data = pd.read_sql(
            sqlalchemy.text(
                f"SELECT * FROM tbAdoptify WHERE uid = {petId}"
            ),
            conn
        )
    return {
        "status": 200,
        "msg": "Success Generate Recommendations",
        "data": data.to_dict('records'),
    }

#API berdasarkan jenis
@app.get("/api/pets-byType")
async def pet_recommendations(petType: str):
    db = connect_unix_socket()
    # db = connect_tcp_socket()
    with db.connect() as conn:
        data = pd.read_sql(
            sqlalchemy.text(
                f"SELECT * FROM tbAdoptify WHERE jenis = '{petType}'"
            ),
            conn
        )
    return {
        "status": 200,
        "msg": "Success Generate Recommendations",
        "data": data.to_dict('records'),
    }

#API berdasarkan ras
@app.get("/api/pets-byRas")
async def pet_recommendations(petType: str):
    db = connect_unix_socket()
    # db = connect_tcp_socket()
    with db.connect() as conn:
        data = pd.read_sql(
            sqlalchemy.text(
                f"SELECT * FROM tbAdoptify WHERE ras = '{petType}'"
            ),
            conn
        )
    return {
        "status": 200,
        "msg": "Success Generate Recommendations",
        "data": data.to_dict('records'),
    }

#API berdasarkan kesehatan
@app.get("/api/pets-byKesehatan")
async def pet_recommendations(petType: str):
    db = connect_unix_socket()
    # db = connect_tcp_socket()
    with db.connect() as conn:
        data = pd.read_sql(
            sqlalchemy.text(
                f"SELECT * FROM tbAdoptify WHERE kesehatan = '{petType}'"
            ),
            conn
        )
    return {
        "status": 200,
        "msg": "Success Generate Recommendations",
        "data": data.to_dict('records'),
    }
    
#API list Shelter
@app.get("/api/shelter")
async def shelter():
    db = connect_unix_socket()
    # db = connect_tcp_socket()
    with db.connect() as conn:
        data = pd.read_sql(
            sqlalchemy.text(
                f"SELECT * FROM tbShelter"
            ),
            conn
        )
    return {
        "status": 200,
        "msg": "Success Generate Recommendations",
        "data": data.to_dict('records'),
    }
    
#API detail Shelter
@app.get("/api/shelter-detail")
async def shelter_recommendations(shelterId: int):
    db = connect_unix_socket()
    # db = connect_tcp_socket()
    with db.connect() as conn:
        data = pd.read_sql(
            sqlalchemy.text(
                f"SELECT * FROM tbShelter WHERE uid = {shelterId}"
            ),
            conn
        )
    return {
        "status": 200,
        "msg": "Success Generate Recommendations",
        "data": data.to_dict('records'),
    }