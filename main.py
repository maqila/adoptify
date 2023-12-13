import pandas as pd
import sqlalchemy
import hashlib
import os

from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from db import connect_tcp_socket
from dotenv import load_dotenv
from sqlalchemy.orm import Session
# from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
# from jose import JWTError, jwt
# from passlib.context import CryptContext
# from datetime import datetime, timedelta

# Load environment variables
dotenv_path = "./.env"
load_dotenv(dotenv_path=dotenv_path)

# Define models for register
class User(BaseModel):
    username: str
    email: str

class RegisterUser(BaseModel):
    username: str
    email: str
    password: str
    
def generate_password_hash(password):
    salt = os.urandom(32)
    hashed_password = hashlib.sha256(password.encode() + salt).hexdigest()
    return f"{hashed_password}:{salt.hex()}"

# Initialize FastAPI app
app = FastAPI()

# Register API
@app.post("/api/register")
async def register(user: RegisterUser, db: Session = Depends(connect_tcp_socket)):
    # Check if username and email are provided
    if not user.username or not user.email:
        raise HTTPException(status_code=400, detail="Missing username or email")

    # Check if email is already registered
    with db.connect() as conn:
        try:
            existing_user = conn.execute(
                sqlalchemy.text(f'SELECT * FROM "user" WHERE "email" = \'{user.email}\';')
            ).fetchone()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error: {e}")

        if existing_user:
            raise HTTPException(status_code=409, detail="Email already registered")

    # Hash password

    hashed_password = generate_password_hash(user.password)

    # Insert user data
    with db.connect() as conn:
        try:
            conn.execute(
                sqlalchemy.text(
                    f'INSERT INTO "user" (username, email, password) VALUES '
                    f"('{user.username}', '{user.email}', '{hashed_password}')"
                )
            )
            conn.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error: {e}")

    return {
        "status": 201,
        "msg": "Successfully registered",
        "data": {
            "username": user.username,
            "email": user.email,
        },
    }

@app.get("/api/pet-recommendations")
async def pet_recommendations(petId: int, recomType: str):
    db = connect_tcp_socket()
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

    if recomType == "ALL":
        df_result = mean_kesehatan_ras_recommendation(petId)
    if recomType == "RAS":
        df_result = ras_hewan_recommendations(petId)
    if recomType == "KESEHATAN":
        df_result = kesehatan_hewan_recommendations(petId)
    if recomType == "JENIS":
        df_result = jenis_hewan_recommendations(petId)
        

    return {
        "status": 200,
        "msg": "Success Generate Recommendations",
        "data": df_result.to_dict("records"),
    }
