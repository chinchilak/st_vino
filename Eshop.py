import streamlit as st
import requests as rq
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import os
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64


DATA = "data.csv"
SECRET_FILE = "client_secret.json"

MAILTO = "chinchilak@gmail.com"
SUBJECT = "Objednávka vína"


def get_g_service(service="gmail",ver="v1",scopes=["https://www.googleapis.com/auth/gmail.readonly","https://www.googleapis.com/auth/gmail.send"]):
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", scopes)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(SECRET_FILE, scopes)
            creds = flow.run_local_server(port=8080)
        # Save the credentials for the next run
    with open("token.json", "w") as token:
        token.write(creds.to_json())
    return build(service, ver, credentials=creds)

def create_message(sender, to, subject, message_text):
  message = MIMEText(message_text, 'html')
  message["to"] = to
  message["from"] = sender
  message["subject"] = subject
  return {"raw": base64.urlsafe_b64encode(message.as_string().encode()).decode()}

def send_message(sender,to,subject,message_text,user_id="me"):
  msg = create_message(sender,to,subject,message_text)
  try:
    service = get_g_service()
    message = (service.users().messages().send(userId=user_id, body=msg).execute())
    print("Message Id: %s" % message["id"])
    return message
  except ValueError as e:
    print("An error occurred: %s" % e)

def get_data_from_web():
    url = "http://vinomikulcik.cz"
    page = rq.get(url)
    soup = BeautifulSoup(page.text, "lxml")
    tables = soup.findAll("table")

    data = []
    for each in tables:
        for i in each.find_all("tr"):
            title = i.text
            data.append(title)

    for item in data:
        if " nabídka vín " in item:
            data.remove(item)

    nlst = []
    for e in data:
        nlst.append(e.split("\n"))

    nlst = [list(filter(None, lst)) for lst in nlst]

    lst1 = []
    lst2 = []
    for a in nlst[::2]:
        lst1.append(a)

    for b in nlst[1::2]:
        lst2.append(b)

    res = []
    for i,j in zip(lst1, lst2):
        res.append(i + j)

    df = pd.DataFrame(res, columns=["ID", "Name", "Pct", "Price", "Description"])
    df = df.fillna(np.NaN)
    df = df.dropna()
    return df

st.set_page_config(page_title="Víno Mikulčík", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
        <style>
            .block-container  {padding-top: 10px;}
            header {visibility: hidden;}
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
        """,
        unsafe_allow_html=True)

st.title("Víno Mikulčík")

st.write("")
btn = st.button("Aktualizovat nabídku")
if btn:
    res = get_data_from_web()
    res.to_csv(DATA, header=True, index=False)

st.write("")

if os.path.isfile(DATA):
    df = pd.read_csv(DATA)
    df["Price"] = df["Price"].str.replace(",-", "")

    for index, row in df.iterrows():
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1,0.5,2.5,0.75,1,1,10])
        with c1:
            val = st.number_input("Quantity", value=0, min_value=0, key="counter"+str(index), label_visibility="collapsed")
        with c2:
            st.write(row[0])
        with c3:
            st.write(row[1].replace(" NOVINKA", ""))
        with c4:
            if " NOVINKA" in row[1]:
                st.write("NOVINKA")
        with c5:
            st.write(row[2])
        with c6:
            st.write(row[3])
        with c7:
            st.write(row[4])

else:
    st.write("No data found")

# sidebar
with st.sidebar:
    totals = []
    for each in st.session_state.items():
        val = each[0]
        if "counter" in val:
            count = int(each[1])
            if count > 0:
                res = []
                idx = int(val.replace("counter",""))
                id = df["ID"].iloc[idx]
                price = int(df["Price"].iloc[idx])        
                res.append(id)
                res.append(count)
                res.append(count * price)
                totals.append(res)

    with st.expander("Přehled objednávky", expanded=True):

        for item in totals:
            st.write(f"{item[1]} x {item[0]}")

        sums = 0
        cnts = 0
        for val in totals:
            sums += int(val[2])
            cnts += int(val[1])

        st.markdown(f"**Počet lahví: {str(cnts)} ks**")
        st.markdown(f"**Celková cena: {str(sums)} Kč**")
        st.write("")

        email = st.text_input("Email *")
        name = st.text_input("Jméno a příjmení")
        address = st.text_input("Adresa")
        phone = st.text_input("Telefon")
        btn_send = st.button("Odeslat objednávku")

        if btn_send:
            if cnts != 0 and sums != 0:
                if "@" in email and "." in email:
                    spacer = "<br>"
                    start = f"""<h3>Přehled objednávky:</h3>"""
                    items = ""
                    for i in totals:
                        items = items + f"{i[1]} x {i[0]}" + "<br>"
                    cntmsg = "<b>" + "Počet lahví: " + str(cnts) + "</b>"
                    summsg = "<b>" + "Celková cena: " + str(sums) + " Kč" + "</b>"
                    endmsg = "<b><br>" + name + "<br>" + address + "<br>" + phone

                    finalmsg = start + items + spacer + cntmsg + spacer + summsg + endmsg

                    send_message(email, MAILTO, SUBJECT, finalmsg)
                    st.success("Objednávka odeslána!")
                    st.info("Objednávka bude potvrzena odpovědí na zadaný email.")
                else:
                    st.warning("Email je povinné pole")
            else:
                st.warning("Objednávka je prázdná!")
        
