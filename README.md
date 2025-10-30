# 🧰 Půjčovna strojů (Streamlit + SQLite)

Moderní webová aplikace pro výpočet půjčovného a správu klientů.

## ⚙️ Funkce
- Výběr klienta a stroje z databáze
- Automatický výpočet půjčovného podle dnů
- Slevy podle typu klienta, věrnosti a promo kódů
- SQLite databáze se vzorovými daty
- Jednoduché a moderní rozhraní ve Streamlitu

## 🚀 Jak spustit online (Streamlit Cloud)
1. Přihlas se na [https://streamlit.io/cloud](https://streamlit.io/cloud)
2. Vyber tento repozitář
3. Do políčka „Main file path“ napiš `streamlit_pujcovna.py`
4. Klikni **Deploy**

## 💻 Jak spustit lokálně
```bash
pip install -r requirements.txt
streamlit run streamlit_pujcovna.py
