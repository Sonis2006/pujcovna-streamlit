import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
from pathlib import Path

# ----- Styling -----
st.set_page_config(page_title="Půjčovna strojů", page_icon="🔧", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(90deg,#f7f9fc,#eef6ff); }
    .title {font-weight:700; color:#0b3d91}
    .card {background: white; padding: 16px; border-radius: 12px; box-shadow: 0 4px 20px rgba(3,18,40,0.08);}
    .small {font-size:0.9rem; color: #6b7280}
    </style>
    """,
    unsafe_allow_html=True,
)

DB_PATH = Path("pujcovna.db")

# ----- Database helpers -----
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # Create tables if not exist
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            daily_rate REAL NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            client_type TEXT NOT NULL, -- individual, business
            loyalty_years INTEGER DEFAULT 0,
            membership INTEGER DEFAULT 0 -- 0/1
        )
        """
    )
    conn.commit()

    # If tables empty, populate sample data
    cur.execute("SELECT COUNT(*) as c FROM machines")
    if cur.fetchone()[0] == 0:
        sample_machines = [
            ("Kompresor 200L","Tichý průmyslový kompresor",450.0),
            ("Bourací kladivo","Výkonný pneumatický kladivo",1200.0),
            ("Elektrokřovinořez","Lehký křovinořez",300.0),
            ("Vibrační deska","Pro zhutnění zeminy",550.0),
            ("Teleskopický manipulátor","Manipulace břemen do 4 t",3500.0),
        ]
        cur.executemany("INSERT INTO machines (name,description,daily_rate) VALUES (?,?,?)", sample_machines)

    cur.execute("SELECT COUNT(*) as c FROM clients")
    if cur.fetchone()[0] == 0:
        sample_clients = [
            ("Jan Novák","individual",2,1),
            ("Stavební firma s.r.o.","business",5,0),
            ("Petra Svobodová","individual",0,0),
            ("Farmářství u lesa","business",1,1),
        ]
        cur.executemany("INSERT INTO clients (name,client_type,loyalty_years,membership) VALUES (?,?,?,?)", sample_clients)

    conn.commit()
    conn.close()

def fetch_machines():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM machines", conn)
    conn.close()
    return df

def fetch_clients():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM clients", conn)
    conn.close()
    return df

# ----- Pricing logic -----
def calculate_price(selected_machine_ids, days, client_row, extra_options=None):
    conn = get_connection()
    cur = conn.cursor()
    if not selected_machine_ids:
        return {"error":"Nebyl vybrán žádný stroj."}

    q = f"SELECT id, name, daily_rate FROM machines WHERE id IN ({','.join(['?']*len(selected_machine_ids))})"
    cur.execute(q, selected_machine_ids)
    machines = cur.fetchall()

    base_per_day = sum(m[2] for m in machines)
    base_total = base_per_day * days

    breakdown = {
        "machines": [{"id": m[0], "name": m[1], "daily_rate": m[2]} for m in machines],
        "days": days,
        "base_per_day": base_per_day,
        "base_total": base_total,
        "discounts": [],
        "final_total": base_total,
    }

    # Volume discount
    if len(machines) >= 3:
        vol_disc = 0.05
        amount = breakdown["final_total"] * vol_disc
        breakdown["discounts"].append(("Sleva za více strojů (3+)", vol_disc, amount))
        breakdown["final_total"] -= amount

    # Long-term rental discount
    if days >= 7 and days < 30:
        long_disc = 0.07
        amount = breakdown["final_total"] * long_disc
        breakdown["discounts"].append(("Sleva za dlouhodobé zapůjčení (7-29 dní)", long_disc, amount))
        breakdown["final_total"] -= amount
    elif days >= 30:
        long_disc = 0.15
        amount = breakdown["final_total"] * long_disc
        breakdown["discounts"].append(("Sleva za dlouhodobé zapůjčení (30+ dní)", long_disc, amount))
        breakdown["final_total"] -= amount

    # Client-specific discounts
    if client_row is not None:
        client_type = client_row["client_type"]
        loyalty = int(client_row.get("loyalty_years", 0))
        membership = bool(client_row.get("membership", 0))

        if client_type == "business":
            corp_disc = 0.08
            amount = breakdown["final_total"] * corp_disc
            breakdown["discounts"].append(("Firemní sleva", corp_disc, amount))
            breakdown["final_total"] -= amount

        if loyalty >= 2:
            step = loyalty // 2
            loyalty_disc = min(0.10, 0.02 * step)
            if loyalty_disc > 0:
                amount = breakdown["final_total"] * loyalty_disc
                breakdown["discounts"].append((f"Věrnostní sleva ({loyalty} let)", loyalty_disc, amount))
                breakdown["final_total"] -= amount

        if membership:
            mem_disc = 0.10
            amount = breakdown["final_total"] * mem_disc
            breakdown["discounts"].append(("Členská sleva", mem_disc, amount))
            breakdown["final_total"] -= amount

    # Promo code
    if extra_options and extra_options.get("promo_code"):
        code = extra_options["promo_code"].strip().upper()
        if code == "JARO10":
            promo = 0.10
            amount = breakdown["final_total"] * promo
            breakdown["discounts"].append(("Promo kód JARO10", promo, amount))
            breakdown["final_total"] -= amount

    # Cap total discounts
    min_total = breakdown["base_total"] * 0.4
    if breakdown["final_total"] < min_total:
        breakdown["discounts"].append(("Maximální limit slev", None, breakdown["final_total"] - min_total))
        breakdown["final_total"] = min_total

    conn.close()
    return breakdown

# ----- App UI -----
init_db()

st.markdown("<h1 class='title'>Půjčovna strojů — kalkulátor půjčovného</h1>", unsafe_allow_html=True)

with st.container():
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Vyberte zákazníka a stroje")

        clients_df = fetch_clients()
        client_options = clients_df["name"].tolist()
        selected_client_name = st.selectbox("Vyberte klienta:", ["-- Nový klient --"] + client_options)

        if selected_client_name and selected_client_name != "-- Nový klient --":
            client_row = clients_df[clients_df["name"] == selected_client_name].iloc[0]
            st.markdown(f"**Typ klienta:** {client_row['client_type'].capitalize()}  ")
            st.markdown(f"**Věrnost (roky):** {client_row['loyalty_years']}  ")
            st.markdown(f"**Členská karta:** {'Ano' if client_row['membership'] else 'Ne'}  ")
        else:
            client_row = None
            with st.expander("Přidat nového klienta"):
                new_name = st.text_input("Jméno klienta")
                new_type = st.selectbox("Typ klienta", ["individual", "business"], index=0)
                new_loyalty = st.number_input("Věrnost (roky)", min_value=0, max_value=50, value=0)
                new_membership = st.checkbox("Má členskou kartu")
                if st.button("Uložit klienta"):
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("INSERT INTO clients (name,client_type,loyalty_years,membership) VALUES (?,?,?,?)",
                                (new_name, new_type, int(new_loyalty), int(new_membership)))
                    conn.commit()
                    conn.close()
                    st.success("Klient uložen — obnovte výběr klienta v seznamu.")

        machines_df = fetch_machines()
        machines_df["label"] = machines_df.apply(lambda r: f"{r['name']} — {r['daily_rate']} Kč/den", axis=1)
        machine_map = dict(zip(machines_df['label'], machines_df['id']))
        selected_labels = st.multiselect("Vyberte stroje k půjčení:", machines_df['label'].tolist())
        selected_machine_ids = [machine_map[l] for l in selected_labels]

        days = st.number_input("Počet dní půjčovného:", min_value=1, max_value=365, value=3)

        with st.expander("Další možnosti a promo kód"):
            promo = st.text_input("Promo kód (volitelně)")
            insurance = st.checkbox("Přidat pojištění (100 Kč/den/objekt)")

        if st.button("Vypočítat cenu"):
            breakdown = calculate_price(selected_machine_ids, int(days), client_row, {"promo_code": promo})
            if "error" in breakdown:
                st.error(breakdown['error'])
            else:
                insurance_cost = 0
                if insurance:
                    insurance_cost = 100 * len(selected_machine_ids) * days
                    breakdown['final_total'] += insurance_cost

                st.success("Výpočet dokončen — níže je rozpis ceny.")

                rcol1, rcol2, rcol3 = st.columns(3)
                rcol1.metric("Základ/den", f"{breakdown['base_per_day']:.0f} Kč")
                rcol2.metric("Základ celkem", f"{breakdown['base_total']:.0f} Kč")
                rcol3.metric("Konečná cena", f"{breakdown['final_total']:.0f} Kč")

                with st.expander("Detailní rozpis slev a položek", expanded=True):
                    st.write("**Vybrané stroje:**")
                    st.table(pd.DataFrame(breakdown['machines']))

                    st.write("**Slevy a úpravy:**")
                    if breakdown['discounts']:
                        disc_table = pd.DataFrame([{"Popis": d[0], "Sleva (%)": (d[1]*100 if d[1] else ''), "Částka (Kč)": round(d[2],2)} for d in breakdown['discounts']])
                        st.table(disc_table)
                    else:
                        st.write("Žádné slevy nebyly aplikovány.")

                    if insurance_cost:
                        st.write(f"Pojištění: {insurance_cost} Kč")

                    st.write(f"**Konečná cena k zaplacení: {breakdown['final_total']:.2f} Kč**")

        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Přehled databáze")
        st.markdown("<div class='small'>Správa dat strojů a klientů — můžete přidávat, editovat nebo mazat záznamy přes SQL níže (pro pokročilé uživatele).</div>", unsafe_allow_html=True)

        with st.expander("Seznam strojů"):
            st.write(machines_df.drop(columns=['label']))
            if st.button("Přidat demo stroj"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("INSERT INTO machines (name,description,daily_rate) VALUES (?,?,?)",
                            ("Nový stroj","Popis nového stroje",999.0))
                conn.commit()
                conn.close()
                st.experimental_rerun()

        with st.expander("Seznam klientů"):
            st.write(clients_df)

        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.markdown("Aplikace vytvořena pro demonstraci správy půjčovny — export/úpravy a další bezpečnostní prvky lze snadno doplnit.")
