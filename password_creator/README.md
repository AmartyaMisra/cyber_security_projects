# 🕷️ SpideyPass — Local Password Generator with Swinging Spider Animation

## 📌 What is it?
**SpideyPass** is a self-contained Python + HTML demo that runs entirely on your machine.  
It opens a **local web page** with:
- A **neon hacker-style password generator**
- A **swinging Spider-Man–like comic animation** outside the main UI  
- Passwords derived **securely** in your browser using **PBKDF2-SHA256**  
- **No external servers, no data sent anywhere** — all offline.

---

## ⚡ How it Works
1. **Python Part**  
   - Writes the HTML/JS/CSS for the UI into a temporary folder.
   - Spins up a **tiny local HTTP server** (built-in to Python).
   - Opens the local web app automatically in your default browser.

2. **Browser Part (HTML + JS)**  
   - Asks you **5 fun questions**: memorable word, number, symbol, wild word, style.
   - Uses **PBKDF2** (Password-Based Key Derivation Function 2) with **SHA-256** hashing to turn your answers + random salt into a **strong password**.
   - Strength meter and random "Spidey quips" make it fun.
   - Salt allows deterministic regeneration — same answers + salt = same password.
   - Three password styles:
     - **Hybrid** (readable + secure)
     - **Crypto** (more random-looking)
     - **Diceware-ish** (readable words)

3. **Spider Animation Layer**  
   - An **SVG-drawn cartoon spider** swings outside the card, occasionally shoots a web, or crawls along edges.
   - Avoids overlapping the UI by calculating safe anchor points.
   - Smooth animation via `requestAnimationFrame`.
   - Tiny synthesized "web whoosh" sound.

---

## 🛡 Security Notes
- PBKDF2 is run **locally** with 150,000 iterations for good strength.
- Nothing is sent to the internet — the server only serves files to **localhost**.
- You can tweak iteration count in code for even stronger keys (may slow down generation).

---

## 🚀 How to Run
```bash
python spiderman_passgen.py
