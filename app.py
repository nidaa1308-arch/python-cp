import streamlit as st
from PIL import Image
import base64

st.set_page_config(
    page_title="TrustCircle",
    page_icon="🛡️",
    layout="wide"
)

# ================= CSS =================
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ================= SESSION =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

# ================= LOGO =================
logo = Image.open("trustcircle_logo.png")

# ================= UI =================
col1, col2, col3 = st.columns([1,2,1])

with col2:
    st.image(logo, width=220)

    st.markdown("<h1 class='title'>TrustCircle</h1>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Login", "Register"])

    # ================= LOGIN =================
    with tab1:
        st.subheader("Login")

        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):

            st.session_state.logged_in = True
            st.session_state.username = email.split("@")[0]

            st.success("Login Successful!")
            st.switch_page("pages/1_Home.py")

    # ================= REGISTER =================
    with tab2:
        st.subheader("Register")

        name = st.text_input("Full Name")
        reg_email = st.text_input("Register Email")
        reg_pass = st.text_input("Create Password", type="password")
        confirm_pass = st.text_input("Confirm Password", type="password")

        if st.button("Register", use_container_width=True):

            if reg_pass != confirm_pass:
                st.error("Passwords do not match")
            else:
                st.success("Registration Successful!")